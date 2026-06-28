"""Orchestration: guard -> signals -> scoring -> label.

classify() is the single entry point. All I/O (LLM call) is isolated here;
all pure logic lives in the imported modules.
"""
import uuid
from datetime import datetime, timezone

from config import SHORT_CIRCUIT_ENABLED, STY_HUMAN_SKIP, REASON_LLM_FAILURE
from stylometric import length_guard, stylometric_score
from llm_signal import llm_score
from scoring import combined_score, confidence_score, classify_label
from labels import label_text


def classify(text: str, llm_client) -> dict:
    """Run the full detection pipeline on text.

    Returns a dict suitable for both the HTTP response and the audit log.
    Raises TextTooShortError (from length_guard) if text is too short.

    On LLM failure, defaults to Uncertain (fail-safe, never defaults to human).
    """
    content_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Guard ---
    reject = length_guard(text)
    if reject:
        raise ValueError(reject)

    # --- Signal 1: stylometric (always runs) ---
    sty = stylometric_score(text)
    if sty is None:
        # length_guard should prevent this; treat as fail-safe
        return {
            "content_id": content_id,
            "timestamp": timestamp,
            "sty_score": None,
            "llm_score": None,
            "combined": None,
            "confidence": None,
            "label_key": "uncertain",
            "audit_reason": "sty_failure",
            "label": label_text("uncertain"),
            "llm_skipped": False,
        }

    # --- Short-circuit: confidently human -> skip LLM ---
    if SHORT_CIRCUIT_ENABLED and sty <= STY_HUMAN_SKIP:
        return {
            "content_id": content_id,
            "timestamp": timestamp,
            "sty_score": round(sty, 4),
            "llm_score": None,
            "combined": round(sty, 4),
            "confidence": round(1.0 - 2.0 * sty, 4),  # single-signal confidence
            "label_key": "likely_human",
            "audit_reason": None,
            "label": label_text("likely_human"),
            "llm_skipped": True,
        }

    # --- Signal 2: LLM (semantic) ---
    llm = llm_score(text, llm_client)

    # --- Fail-safe: LLM failure -> Uncertain ---
    if llm is None:
        return {
            "content_id": content_id,
            "timestamp": timestamp,
            "sty_score": round(sty, 4),
            "llm_score": None,
            "combined": None,
            "confidence": None,
            "label_key": "uncertain",
            "audit_reason": REASON_LLM_FAILURE,
            "label": label_text("uncertain"),
            "llm_skipped": False,
        }

    # --- Scoring ---
    comb = combined_score(sty, llm)
    conf = confidence_score(sty, llm)
    label_key, audit_reason = classify_label(sty, llm)

    return {
        "content_id": content_id,
        "timestamp": timestamp,
        "sty_score": round(sty, 4),
        "llm_score": round(llm, 4),
        "combined": round(comb, 4),
        "confidence": round(conf, 4),
        "label_key": label_key,
        "audit_reason": audit_reason,
        "label": label_text(label_key),
        "llm_skipped": False,
    }
