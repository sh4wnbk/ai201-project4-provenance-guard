"""M3 verification: burstiness and stylometric_score against rubric inputs."""
import pytest
from stylometric import burstiness, stylometric_score, length_guard

# Rubric inputs — substitute the actual texts used in planning.md validation.
# Target burstiness values: clear_ai=0.379, clear_human=0.611,
#                           formal_human=0.256, lightly_edited_ai=0.382
CLEAR_AI = "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."

CLEAR_HUMAN = "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"

FORMAL_HUMAN = "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."

LIGHTLY_EDITED_AI = "I've been thinking a lot about remote work lately. There are genuine tradeoffs - flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type."

RUBRIC = [
    (CLEAR_AI,         0.379, 0.700),
    (CLEAR_HUMAN,      0.611, 0.126),
    (FORMAL_HUMAN,     0.256, 0.911),
    (LIGHTLY_EDITED_AI, 0.382, 0.693),
]


@pytest.mark.parametrize("text,expected_burst,expected_sty", RUBRIC)
def test_rubric_burstiness(text, expected_burst, expected_sty):
    if not text:
        pytest.skip("Rubric text not yet populated")
    assert abs(burstiness(text) - expected_burst) < 0.01


@pytest.mark.parametrize("text,expected_burst,expected_sty", RUBRIC)
def test_rubric_sty_score(text, expected_burst, expected_sty):
    if not text:
        pytest.skip("Rubric text not yet populated")
    assert abs(stylometric_score(text) - expected_sty) < 0.01


# --- Length guard ---

def test_length_guard_rejects_single_sentence():
    assert length_guard("This is one sentence.") is not None


def test_length_guard_rejects_too_few_words():
    assert length_guard("Short text. Also short.") is not None


def test_length_guard_passes_valid_text():
    text = (
        "The quick brown fox jumps over the lazy dog. "
        "A second sentence follows with more words to satisfy the guard. "
        "And a third for good measure, adding length to this test input."
    )
    assert length_guard(text) is None


def test_burstiness_returns_none_for_single_sentence():
    assert burstiness("Only one sentence here with many words in it.") is None


def test_stylometric_score_range():
    text = (
        "The quick brown fox jumps over the lazy dog. "
        "A second sentence follows with many words to make the guard pass. "
        "Here is a third sentence that is much much much much much much longer than the others."
    )
    score = stylometric_score(text)
    assert 0.0 <= score <= 1.0
