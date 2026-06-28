"""Structural signal — pure Python, no network."""
import re
import math
import statistics as st

from config import BURSTINESS_CENTER, BURSTINESS_STEEPNESS, MIN_SENTENCES, MIN_WORDS


def split_sentences(text):
    return [s for s in re.split(r'[.!?]+', text) if s.strip()]


def tokenize(text):
    return re.findall(r"[a-z']+", text.lower())


def burstiness(text):
    lengths = [len(tokenize(s)) for s in split_sentences(text)]
    if len(lengths) < 2:
        return None
    mean = st.mean(lengths)
    return st.pstdev(lengths) / mean if mean else 0.0


def stylometric_score(text, c=BURSTINESS_CENTER, k=BURSTINESS_STEEPNESS):
    b = burstiness(text)
    if b is None:
        return None
    return 1.0 / (1.0 + math.exp(k * (b - c)))


def length_guard(text: str) -> str | None:
    """Return a rejection reason string if text is too short, else None."""
    sents = split_sentences(text)
    words = sum(len(tokenize(s)) for s in sents)
    if len(sents) < MIN_SENTENCES:
        return f"too few sentences: {len(sents)} (minimum {MIN_SENTENCES})"
    if words < MIN_WORDS:
        return f"too few words: {words} (minimum {MIN_WORDS})"
    return None
