"""M3 verification: audit log and status store invariants."""
import pytest
from store import Store


@pytest.fixture
def db(tmp_path):
    return Store(str(tmp_path / "test.db"))


def _entry(content_id="abc123", **kwargs):
    return {
        "content_id": content_id,
        "entry_type": "classification",
        "timestamp": "2026-01-01T00:00:00+00:00",
        **kwargs,
    }


def test_appended_entry_is_retrievable(db):
    db.append_log(_entry())
    log = db.get_log()
    assert len(log) == 1
    assert log[0]["content_id"] == "abc123"


def test_set_status_get_status_round_trip(db):
    db.set_status("abc123", "classified")
    assert db.get_status("abc123") == "classified"


def test_status_update(db):
    db.set_status("abc123", "classified")
    db.set_status("abc123", "under_review")
    assert db.get_status("abc123") == "under_review"


def test_appeal_appends_new_row_leaves_original_intact(db):
    db.append_log(_entry())
    original = db.get_log_entry("abc123")

    db.append_log({
        "content_id": "abc123",
        "entry_type": "appeal",
        "creator_reasoning": "I wrote this myself.",
        "timestamp": "2026-01-01T01:00:00+00:00",
    })

    log = db.get_log(limit=10)
    assert len(log) == 2
    # Original classification entry unchanged
    assert db.get_log_entry("abc123") == original
    # Appeal is a separate row
    appeal_rows = [e for e in log if e.get("entry_type") == "appeal"]
    assert len(appeal_rows) == 1
    assert appeal_rows[0]["creator_reasoning"] == "I wrote this myself."


def test_status_flips_independently_of_log(db):
    db.set_status("abc123", "classified")
    db.set_status("abc123", "under_review")
    assert db.get_status("abc123") == "under_review"
    assert db.get_log() == []


def test_get_log_entry_returns_none_for_unknown(db):
    assert db.get_log_entry("unknown") is None


def test_known_content_id_false_for_missing(db):
    assert not db.known_content_id("does-not-exist")


def test_get_log_respects_limit(db):
    for i in range(5):
        db.append_log(_entry(content_id=f"id{i}"))
    assert len(db.get_log(limit=3)) == 3


def test_two_instances_are_isolated(tmp_path):
    s1 = Store(str(tmp_path / "a.db"))
    s2 = Store(str(tmp_path / "b.db"))
    s1.append_log(_entry(content_id="x1"))
    assert s2.get_log() == []
