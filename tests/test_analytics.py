"""Analytics aggregation tests — hand-built entry lists, no DB."""
import pytest
from analytics import compute_analytics
from config import UNCERTAIN_REASONS


def _cls(content_id, label_key, audit_reason=None):
    return {
        "entry_type": "classification",
        "content_id": content_id,
        "label_key": label_key,
        "audit_reason": audit_reason,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


def _appeal(content_id):
    return {
        "entry_type": "appeal",
        "content_id": content_id,
        "creator_reasoning": "I wrote this.",
        "timestamp": "2026-01-01T01:00:00+00:00",
    }


# --- Empty log ---

def test_empty_log_returns_zeros():
    result = compute_analytics([])
    assert result["total_classifications"] == 0
    assert result["appeal_rate"] == 0.0
    assert result["appealed_count"] == 0
    for label in ("likely_ai", "likely_human", "uncertain"):
        assert result["verdict_distribution"][label]["count"] == 0
        assert result["verdict_distribution"][label]["fraction"] == 0.0
    for reason in UNCERTAIN_REASONS:
        assert result["uncertain_breakdown"][reason]["count"] == 0
        assert result["uncertain_breakdown"][reason]["fraction"] == 0.0


# --- Verdict distribution ---

MIXED = [
    _cls("a1", "likely_ai"),
    _cls("a2", "likely_ai"),
    _cls("h1", "likely_human"),
    _cls("u1", "uncertain", "weak_corroboration"),
    _cls("u2", "uncertain", "disagreement"),
    _cls("u3", "uncertain", "weak_evidence"),
    _cls("u4", "uncertain", "llm_failure"),
    _appeal("a1"),          # appeal on one AI result
    _appeal("u1"),          # appeal on one uncertain result
    _appeal("u1"),          # second appeal on same id — must not double-count
]


def test_verdict_distribution_counts():
    r = compute_analytics(MIXED)
    vd = r["verdict_distribution"]
    assert vd["likely_ai"]["count"] == 2
    assert vd["likely_human"]["count"] == 1
    assert vd["uncertain"]["count"] == 4


def test_verdict_distribution_fractions():
    r = compute_analytics(MIXED)
    vd = r["verdict_distribution"]
    assert vd["likely_ai"]["fraction"] == pytest.approx(2 / 7)
    assert vd["likely_human"]["fraction"] == pytest.approx(1 / 7)
    assert vd["uncertain"]["fraction"] == pytest.approx(4 / 7)


def test_fractions_sum_to_one():
    r = compute_analytics(MIXED)
    vd = r["verdict_distribution"]
    total = sum(vd[k]["fraction"] for k in ("likely_ai", "likely_human", "uncertain"))
    assert total == pytest.approx(1.0)


# --- Appeal rate ---

def test_appeal_rate_counts_distinct_ids():
    r = compute_analytics(MIXED)
    # a1 and u1 appealed (u1 appealed twice — counts as one)
    assert r["appealed_count"] == 2
    assert r["appeal_rate"] == pytest.approx(2 / 7)


def test_appeal_rate_zero_when_no_appeals():
    entries = [_cls("x1", "likely_ai"), _cls("x2", "likely_human")]
    r = compute_analytics(entries)
    assert r["appeal_rate"] == 0.0
    assert r["appealed_count"] == 0


# --- Uncertain breakdown ---

def test_uncertain_breakdown_all_reasons():
    r = compute_analytics(MIXED)
    ub = r["uncertain_breakdown"]
    assert ub["weak_corroboration"]["count"] == 1
    assert ub["disagreement"]["count"] == 1
    assert ub["weak_evidence"]["count"] == 1
    assert ub["llm_failure"]["count"] == 1


def test_uncertain_breakdown_fractions():
    r = compute_analytics(MIXED)
    ub = r["uncertain_breakdown"]
    for reason in ("weak_corroboration", "disagreement", "weak_evidence", "llm_failure"):
        assert ub[reason]["fraction"] == pytest.approx(1 / 4)


def test_uncertain_breakdown_all_zeros_when_no_uncertain():
    entries = [_cls("x", "likely_ai"), _cls("y", "likely_human")]
    r = compute_analytics(entries)
    ub = r["uncertain_breakdown"]
    for reason in UNCERTAIN_REASONS:
        assert ub[reason]["count"] == 0
        assert ub[reason]["fraction"] == 0.0


def test_total_classifications_excludes_appeals():
    r = compute_analytics(MIXED)
    assert r["total_classifications"] == 7  # 7 classifications, 3 appeals
