"""Semantic signal — Cerebras LLM classification."""
import json
import logging

from config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert at distinguishing human-written text from AI-generated text.
Assess the text delimited by <text></text> tags and return a JSON object with
exactly one key: "ai_score", a float in [0.0, 1.0].

0.0 = definitely human-written
1.0 = definitely AI-generated

Return ONLY the JSON object. No explanation, no markdown, no other keys.\
"""


def llm_score(text: str, client) -> float | None:
    """Return an AI-likelihood score in [0, 1], or None on any failure.

    None triggers the fail-safe (Uncertain) in the pipeline.
    Client is a parameter so this function is unit-testable without a live call.
    """
    user_content = f"<text>{text}</text>"
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_completion_tokens=LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        score = float(data["ai_score"])
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"ai_score out of range: {score}")
        return score
    except Exception as exc:
        logger.error("llm_score failed: %s", exc)
        return None
