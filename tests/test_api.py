"""M5 API-level tests — Flask test client, no live LLM calls."""
import os
os.environ.setdefault("CEREBRAS_API_KEY", "test")

import json
import pytest
from unittest.mock import patch, MagicMock

from store import Store

# Text that passes the length guard and lands "likely_ai" with llm=0.85
CLEAR_AI = (
    "Artificial intelligence represents a transformative paradigm shift in modern society. "
    "It is important to note that while the benefits of AI are numerous, it is equally "
    "essential to consider the ethical implications. Furthermore, stakeholders across "
    "various sectors must collaborate to ensure responsible deployment."
)

# Text with high burstiness — short-circuits to likely_human without an LLM call
CLEAR_HUMAN = (
    "ok so i finally tried that new ramen place downtown and honestly? underwhelming. "
    "the broth was fine but they put WAY too much sodium in it and i was thirsty for "
    "like three hours after. my friend got the spicy version and said it was better. "
    "probably won't go back unless someone drags me there"
)


@pytest.fixture(autouse=True)
def fresh_store(tmp_path):
    import app as flask_app
    s = Store(str(tmp_path / "test.db"))
    flask_app.store = s
    yield s


@pytest.fixture()
def api(fresh_store):
    """Test client with LLM mocked and rate limiting reset."""
    with patch("cerebras.cloud.sdk.Cerebras", MagicMock()), \
         patch("pipeline.llm_score", return_value=0.85):
        import app as flask_app
        flask_app.limiter._storage.reset()
        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as client:
            yield client


def _submit(client, text=CLEAR_AI, creator_id="user1"):
    return client.post(
        "/submit",
        data=json.dumps({"text": text, "creator_id": creator_id}),
        content_type="application/json",
    )


def _appeal(client, content_id, reasoning="I wrote this myself."):
    return client.post(
        "/appeal",
        data=json.dumps({"content_id": content_id, "creator_reasoning": reasoning}),
        content_type="application/json",
    )


# --- /submit ---

def test_submit_returns_content_id(api):
    resp = _submit(api)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "content_id" in body
    assert len(body["content_id"]) == 32  # uuid4 hex


def test_submit_ai_text_returns_likely_ai(api):
    body = _submit(api).get_json()
    assert body["label_key"] == "likely_ai"


def test_submit_human_text_returns_likely_human(api):
    body = _submit(api, text=CLEAR_HUMAN).get_json()
    assert body["label_key"] == "likely_human"


def test_submit_label_text_varies_by_result(api):
    ai_label = _submit(api, text=CLEAR_AI).get_json()["label"]
    human_label = _submit(api, text=CLEAR_HUMAN).get_json()["label"]
    assert ai_label != human_label
    assert "automated signal" in ai_label        # likely_ai variant
    assert "natural variation" in human_label    # likely_human variant


def test_submit_short_text_returns_422(api):
    resp = _submit(api, text="Too short.")
    assert resp.status_code == 422


# --- /appeal ---

def test_appeal_unknown_content_id_returns_404(api):
    resp = _appeal(api, "nonexistent-id")
    assert resp.status_code == 404


def test_appeal_flips_status_to_under_review(api, fresh_store):
    content_id = _submit(api).get_json()["content_id"]
    resp = _appeal(api, content_id)
    assert resp.status_code == 200
    assert fresh_store.get_status(content_id) == "under_review"


def test_appeal_appends_log_row_leaves_original_intact(api, fresh_store):
    content_id = _submit(api).get_json()["content_id"]
    original = fresh_store.get_log_entry(content_id)

    _appeal(api, content_id)

    log = fresh_store.get_log(limit=10)
    entry_types = [e["entry_type"] for e in log]
    assert "classification" in entry_types
    assert "appeal" in entry_types
    # Original classification row is byte-identical
    assert fresh_store.get_log_entry(content_id) == original


def test_status_flips_independently_of_log_content(api, fresh_store):
    content_id = _submit(api).get_json()["content_id"]
    assert fresh_store.get_status(content_id) == "classified"
    _appeal(api, content_id)
    assert fresh_store.get_status(content_id) == "under_review"
    # Log still has the original classification entry
    assert fresh_store.get_log_entry(content_id)["entry_type"] == "classification"


# --- Rate limiting ---

def test_rate_limit_returns_429_after_10_requests(api):
    responses = [
        _submit(api, creator_id=f"u{i}").status_code
        for i in range(12)
    ]
    assert 429 in responses
    # Everything before the first 429 must be 200
    first_429 = responses.index(429)
    assert all(s == 200 for s in responses[:first_429])
