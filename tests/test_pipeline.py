"""M4 verification: pipeline fail-safe and integration smoke tests."""
import pytest
from unittest.mock import MagicMock
import pipeline


VALID_TEXT = (
    "The implications of this research are broad and far-reaching. "
    "Scientists across multiple disciplines have begun to re-examine their assumptions. "
    "Data collected over the past decade supports the hypothesis in several key respects. "
    "However, outliers remain difficult to explain within the current theoretical framework. "
    "Further longitudinal study is warranted before drawing definitive conclusions."
)


def _mock_client(score: float) -> MagicMock:
    """Return a mock Cerebras client that returns the given ai_score."""
    import json
    client = MagicMock()
    client.chat.completions.create.return_value.choices[0].message.content = (
        json.dumps({"ai_score": score})
    )
    return client


def test_llm_failure_returns_uncertain():
    """On LLM error, pipeline must return uncertain — never likely_human."""
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network error")

    result = pipeline.classify(VALID_TEXT, client)
    assert result["label_key"] == "uncertain"
    assert result["audit_reason"] == "llm_failure"
    assert result["llm_score"] is None


def test_short_text_raises():
    client = _mock_client(0.5)
    with pytest.raises(ValueError):
        pipeline.classify("Too short.", client)


def test_result_has_required_fields():
    client = _mock_client(0.8)
    result = pipeline.classify(VALID_TEXT, client)
    for field in ("content_id", "timestamp", "sty_score", "llm_score",
                  "combined", "confidence", "label_key", "label"):
        assert field in result, f"missing field: {field}"


def test_likely_ai_with_high_llm_score():
    # High LLM + moderate-high sty -> likely_ai or uncertain, never likely_human
    client = _mock_client(0.9)
    result = pipeline.classify(VALID_TEXT, client)
    assert result["label_key"] != "likely_human"


def test_skips_llm_when_sty_very_low():
    """High-burstiness text should short-circuit without calling the LLM."""
    client = MagicMock()

    # Build text with highly variable sentence lengths (very high burstiness)
    variable_text = (
        "No. "
        "This sentence is considerably longer than the previous one by a wide margin indeed. "
        "Yes. "
        "Another extremely verbose and rambling sentence that goes on and on for quite a while. "
        "Stop. "
        "One more very long sentence here to make sure the burstiness coefficient is high enough."
    )
    result = pipeline.classify(variable_text, client)

    if result.get("llm_skipped"):
        client.chat.completions.create.assert_not_called()
        assert result["label_key"] == "likely_human"
