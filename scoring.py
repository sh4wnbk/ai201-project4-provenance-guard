"""Pure scoring functions — no I/O, no state."""
from config import (
    T_HIGH, DISAGREE, LLM_CORROBORATE_MIN,
    REASON_WEAK_CORROBORATION, REASON_DISAGREEMENT, REASON_WEAK_EVIDENCE,
)


def combined_score(sty: float, llm: float) -> float:
    """Average the two signals. Sets the direction of the verdict."""
    return (sty + llm) / 2.0


def confidence_score(sty: float, llm: float) -> float:
    """Verdict strength.

    High only when both signals agree AND the average is far from 0.5.
    Signals disagreeing (one high, one low) drives this toward 0 even if
    the average looks decisive — preventing a confident mislabel.
    """
    agreement = 1.0 - abs(sty - llm)
    strength = 2.0 * abs(combined_score(sty, llm) - 0.5)
    return agreement * strength


def classify_label(sty: float, llm: float) -> tuple[str, str | None]:
    """Return (label_key, audit_reason).

    Precedence:
    1. Asymmetric guard: sty > 0.5 (stylometric accuses) but llm < LLM_CORROBORATE_MIN
       (LLM doesn't strongly corroborate) → Uncertain, "weak_corroboration".
       Guards the harm direction: the system won't accuse without LLM confirmation.
    2. Confidence gate: both signals agree strongly → Likely AI / Likely human.
    3. Fallback Uncertain with disagreement or weak_evidence reason.
    """
    # Step 1 — asymmetric fairness guard
    if sty > 0.5 and llm < LLM_CORROBORATE_MIN:
        return "uncertain", REASON_WEAK_CORROBORATION

    # Step 2 — confidence gate
    comb = combined_score(sty, llm)
    conf = confidence_score(sty, llm)
    if conf >= T_HIGH:
        if comb > 0.5:
            return "likely_ai", None
        else:
            return "likely_human", None

    # Step 3 — uncertain; record why
    if abs(sty - llm) >= DISAGREE:
        return "uncertain", REASON_DISAGREEMENT
    return "uncertain", REASON_WEAK_EVIDENCE
