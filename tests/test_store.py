"""M3 verification: audit log and status store invariants."""
import pytest
import store


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    store.init_db(str(tmp_path / "test.db"))
    yield


def _entry(content_id="abc123", **kwargs):
    return {
        "content_id": content_id,
        "entry_type": "classification",
        "timestamp": "2026-01-01T00:00:00+00:00",
        **kwargs,
    }


def test_appended_entry_is_retrievable():
    store.append_log(_entry())
    log = store.get_log()
    assert len(log) == 1
    assert log[0]["content_id"] == "abc123"


def test_set_status_get_status_round_trip():
    store.set_status("abc123", "classified")
    assert store.get_status("abc123") == "classified"


def test_status_update():
    store.set_status("abc123", "classified")
    store.set_status("abc123", "under_review")
    assert store.get_status("abc123") == "under_review"


def test_appeal_appends_new_row_leaves_original_intact():
    store.append_log(_entry())
    original = store.get_log_entry("abc123")

    store.append_log({
        "content_id": "abc123",
        "entry_type": "appeal",
        "creator_reasoning": "I wrote this myself.",
        "timestamp": "2026-01-01T01:00:00+00:00",
    })

    log = store.get_log(limit=10)
    assert len(log) == 2
    # Original classification entry unchanged
    assert store.get_log_entry("abc123") == original
    # Appeal is a separate row
    appeal_rows = [e for e in log if e.get("entry_type") == "appeal"]
    assert len(appeal_rows) == 1
    assert appeal_rows[0]["creator_reasoning"] == "I wrote this myself."


def test_status_flips_independently_of_log():
    store.set_status("abc123", "classified")
    store.set_status("abc123", "under_review")
    assert store.get_status("abc123") == "under_review"
    assert store.get_log() == []


def test_get_log_entry_returns_none_for_unknown():
    assert store.get_log_entry("unknown") is None


def test_known_content_id_false_for_missing():
    assert not store.known_content_id("does-not-exist")


def test_get_log_respects_limit():
    for i in range(5):
        store.append_log(_entry(content_id=f"id{i}"))
    assert len(store.get_log(limit=3)) == 3
