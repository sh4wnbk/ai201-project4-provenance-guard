"""All three label variants are reachable and match locked text."""
import pytest
from labels import label_text

def test_likely_ai_contains_appeal_path():
    text = label_text("likely_ai")
    assert "ask us to review" in text

def test_likely_human_has_no_appeal_path():
    text = label_text("likely_human")
    assert "review" not in text.lower()

def test_uncertain_mentions_populations():
    text = label_text("uncertain")
    assert "formal" in text or "technical" in text or "non-native" in text

def test_uncertain_states_nothing_recorded():
    text = label_text("uncertain")
    assert "nothing has been recorded" in text.lower()

def test_unknown_key_raises():
    with pytest.raises(ValueError):
        label_text("bogus")

def test_all_keys_return_nonempty_strings():
    for key in ("likely_ai", "likely_human", "uncertain"):
        assert isinstance(label_text(key), str)
        assert len(label_text(key)) > 0
