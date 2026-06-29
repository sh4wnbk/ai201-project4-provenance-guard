"""Flask routes — thin layer only. No business logic here."""
import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from store import Store
import pipeline
import analytics
from stylometric import length_guard
from config import RATE_LIMITS, DB_PATH

load_dotenv(Path(__file__).parent / ".env")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
store = Store(DB_PATH)
_client = Cerebras(api_key=os.environ["CEREBRAS_API_KEY"])

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://",
    default_limits=[],
)


@app.route("/submit", methods=["POST"])
@limiter.limit(RATE_LIMITS)
def submit():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()
    creator_id = body.get("creator_id", "").strip()

    if not text:
        return jsonify({"error": "text is required"}), 400
    if not creator_id:
        return jsonify({"error": "creator_id is required"}), 400

    reject = length_guard(text)
    if reject:
        return jsonify({"error": reject}), 422

    result = pipeline.classify(text, _client)

    log_entry = {**result, "creator_id": creator_id, "entry_type": "classification"}
    store.append_log(log_entry)
    store.set_status(result["content_id"], "classified")

    return jsonify({
        "content_id": result["content_id"],
        "label_key": result["label_key"],
        "label": result["label"],
        "confidence": result["confidence"],
        "combined": result["combined"],
        "sty_score": result["sty_score"],
        "llm_score": result["llm_score"],
        "audit_reason": result["audit_reason"],
    }), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = body.get("content_id", "").strip()
    creator_reasoning = body.get("creator_reasoning", "").strip()

    if not content_id:
        return jsonify({"error": "content_id is required"}), 400
    if not creator_reasoning:
        return jsonify({"error": "creator_reasoning is required"}), 400

    if not store.known_content_id(content_id):
        return jsonify({"error": "content_id not found"}), 404

    store.set_status(content_id, "under_review")
    store.append_log({
        "content_id": content_id,
        "entry_type": "appeal",
        "creator_reasoning": creator_reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Your appeal has been received and will be reviewed.",
    }), 200


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", 50, type=int)
    return jsonify(store.get_log(limit)), 200


@app.route("/analytics", methods=["GET"])
def analytics_view():
    entries = store.get_log(limit=10_000)
    return jsonify(analytics.compute_analytics(entries)), 200


if __name__ == "__main__":
    app.run(debug=True)
