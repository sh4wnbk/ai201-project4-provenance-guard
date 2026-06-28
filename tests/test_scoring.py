"""M4 verification: scoring reproduces the validation table."""
import pytest
from scoring import combined_score, confidence_score, classify_label

# llm values are measured Cerebras scores (not estimates):
#   clear_ai  llm=0.780 (measured), clear_human llm=0.15 (estimated low),
#   formal_human llm=0.600 (measured), lightly_edited_ai llm=0.55 (estimated)
RUBRIC = [
    # (name,              sty,   llm,   exp_combined, exp_conf, exp_label,      exp_reason)
    ("clear_ai",          0.700, 0.780, 0.740,        0.448,    "likely_ai",    None),
    ("clear_human",       0.126, 0.15,  0.138,        0.707,    "likely_human", None),
    ("formal_human",      0.911, 0.600, 0.756,        0.352,    "uncertain",    "weak_corroboration"),
    ("lightly_edited_ai", 0.693, 0.55,  0.622,        0.208,    "uncertain",    "weak_corroboration"),
]


@pytest.mark.parametrize("name,sty,llm,exp_comb,exp_conf,exp_label,exp_reason", RUBRIC)
def test_combined_score(name, sty, llm, exp_comb, exp_conf, exp_label, exp_reason):
    assert abs(combined_score(sty, llm) - exp_comb) < 0.01, name


@pytest.mark.parametrize("name,sty,llm,exp_comb,exp_conf,exp_label,exp_reason", RUBRIC)
def test_confidence_score(name, sty, llm, exp_comb, exp_conf, exp_label, exp_reason):
    assert abs(confidence_score(sty, llm) - exp_conf) < 0.01, name


@pytest.mark.parametrize("name,sty,llm,exp_comb,exp_conf,exp_label,exp_reason", RUBRIC)
def test_classify_label(name, sty, llm, exp_comb, exp_conf, exp_label, exp_reason):
    label_key, reason = classify_label(sty, llm)
    assert label_key == exp_label, name
    assert reason == exp_reason, name


# --- Asymmetric guard tests ---

def test_guard_fires_when_llm_below_threshold():
    # sty accuses (> 0.5), LLM doesn't strongly corroborate (< 0.70) → Uncertain
    label, reason = classify_label(0.8, 0.65)
    assert label == "uncertain"
    assert reason == "weak_corroboration"


def test_guard_does_not_fire_when_llm_meets_threshold():
    # sty accuses (> 0.5), LLM corroborates (≥ 0.70) → guard clears, verdict stands
    label, reason = classify_label(0.8, 0.75)
    assert label == "likely_ai"
    assert reason is None


def test_guard_does_not_apply_when_sty_human():
    # sty below 0.5 → guard never fires; weak_corroboration should not appear
    _, reason = classify_label(0.3, 0.65)
    assert reason != "weak_corroboration"


# --- Existing invariants ---

def test_disagreement_drives_confidence_down():
    conf = confidence_score(0.0, 1.0)
    assert conf < 0.05


def test_agreement_at_boundary():
    assert confidence_score(0.5, 0.5) == pytest.approx(0.0)
