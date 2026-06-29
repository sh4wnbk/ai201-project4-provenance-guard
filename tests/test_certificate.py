"""Provenance certificate: creator verification flow tests."""
import os
os.environ.setdefault("CEREBRAS_API_KEY", "test")

import json
import pytest
from unittest.mock import patch, MagicMock

from store import Store
from config import CERTIFICATE_TEXT
import labels as label_module

SAMPLE_TEXT = (
    "I have been writing about monetary policy for fifteen years. "
    "The relationship between interest rates and asset prices is complex and often "
    "misunderstood. My work draws on primary sources and field interviews, not summaries."
)


@pytest.fixture(autouse=True)
def fresh_store(tmp_path):
    import app as flask_app
    s = Store(str(tmp_path / "test.db"))
    flask_app.store = s
    yield s


@pytest.fixture()
def api(fresh_store):
    with patch("cerebras.cloud.sdk.Cerebras", MagicMock()), \
         patch("pipeline.llm_score", return_value=0.50):
        import app as flask_app
        flask_app.limiter._storage.reset()
        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as client:
            yield client


def _verify(client, creator_id="alice", sample_text=SAMPLE_TEXT,
            attestation="I wrote this myself."):
    return client.post(
        "/verify",
        data=json.dumps({
            "creator_id": creator_id,
            "sample_text": sample_text,
            "attestation": attestation,
        }),
        content_type="application/json",
    )


def _review(client, creator_id="alice", approve=True):
    return client.post(
        "/verify/review",
        data=json.dumps({"creator_id": creator_id, "approve": approve}),
        content_type="application/json",
    )


def _submit(client, creator_id="alice"):
    text = (
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment."
    )
    return client.post(
        "/submit",
        data=json.dumps({"text": text, "creator_id": creator_id}),
        content_type="application/json",
    )


# --- Store-level creator status ---

def test_creator_status_defaults_to_unverified(fresh_store):
    assert fresh_store.get_creator_status("nobody") == "unverified"


def test_creator_status_round_trip(fresh_store):
    fresh_store.set_creator_status("alice", "pending_review")
    assert fresh_store.get_creator_status("alice") == "pending_review"


def test_creator_status_update(fresh_store):
    fresh_store.set_creator_status("alice", "pending_review")
    fresh_store.set_creator_status("alice", "verified_human")
    assert fresh_store.get_creator_status("alice") == "verified_human"


# --- POST /verify ---

def test_verify_sets_pending_review(api, fresh_store):
    resp = _verify(api)
    assert resp.status_code == 200
    assert fresh_store.get_creator_status("alice") == "pending_review"


def test_verify_response_contains_advisory(api):
    body = _verify(api).get_json()
    assert body["status"] == "pending_review"
    assert "advisory_label_key" in body


def test_verify_logs_advisory_read(api, fresh_store):
    _verify(api)
    log = fresh_store.get_log(limit=10)
    vr = [e for e in log if e.get("entry_type") == "verification_request"]
    assert len(vr) == 1
    assert "advisory_label_key" in vr[0]
    assert "advisory_confidence" in vr[0]


def test_verify_advisory_does_not_change_status_to_verified(api, fresh_store):
    _verify(api)
    # Advisory read must never auto-verify — only human review can
    assert fresh_store.get_creator_status("alice") != "verified_human"


def test_verify_missing_attestation_returns_400(api):
    resp = api.post(
        "/verify",
        data=json.dumps({"creator_id": "alice", "sample_text": SAMPLE_TEXT}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_verify_short_sample_returns_422(api):
    resp = api.post(
        "/verify",
        data=json.dumps({
            "creator_id": "alice",
            "sample_text": "Too short.",
            "attestation": "I wrote this.",
        }),
        content_type="application/json",
    )
    assert resp.status_code == 422


# --- POST /verify/review ---

def test_review_approve_sets_verified_human(api, fresh_store):
    _verify(api)
    _review(api, approve=True)
    assert fresh_store.get_creator_status("alice") == "verified_human"


def test_review_deny_sets_denied(api, fresh_store):
    _verify(api)
    _review(api, approve=False)
    assert fresh_store.get_creator_status("alice") == "denied"


def test_review_logs_decision(api, fresh_store):
    _verify(api)
    _review(api, approve=True)
    log = fresh_store.get_log(limit=10)
    decisions = [e for e in log if e.get("entry_type") == "verification_review"]
    assert len(decisions) == 1
    assert decisions[0]["decision"] == "verified_human"


def test_review_missing_approve_returns_400(api):
    resp = api.post(
        "/verify/review",
        data=json.dumps({"creator_id": "alice"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


# --- Certificate in /submit ---

def test_verified_creator_submit_includes_certificate(api, fresh_store):
    _verify(api)
    _review(api, approve=True)
    body = _submit(api).get_json()
    assert "certificate" in body
    assert body["certificate"] == CERTIFICATE_TEXT


def test_unverified_creator_submit_has_no_certificate(api):
    body = _submit(api, creator_id="stranger").get_json()
    assert "certificate" not in body


def test_certificate_text_distinct_from_all_label_variants(api, fresh_store):
    _verify(api)
    _review(api, approve=True)
    cert = _submit(api).get_json()["certificate"]
    for key in ("likely_ai", "likely_human", "uncertain"):
        assert cert != label_module.label_text(key)
