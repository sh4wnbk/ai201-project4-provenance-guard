"""Unit tests for llm_score — no live API calls."""
import json
import pytest
from unittest.mock import MagicMock
from llm_signal import llm_score


def _client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value.choices[0].message.content = content
    return client


def test_returns_float_in_range():
    score = llm_score("Some text.", _client('{"ai_score": 0.75}'))
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_parses_score_correctly():
    assert llm_score("text", _client('{"ai_score": 0.3}')) == pytest.approx(0.3)


def test_returns_none_on_network_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("timeout")
    assert llm_score("text", client) is None


def test_returns_none_on_invalid_json():
    assert llm_score("text", _client("not json")) is None


def test_returns_none_on_missing_key():
    assert llm_score("text", _client('{"score": 0.5}')) is None


def test_returns_none_on_out_of_range_score():
    assert llm_score("text", _client('{"ai_score": 1.5}')) is None
