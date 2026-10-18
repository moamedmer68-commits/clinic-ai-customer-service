import sys
from types import SimpleNamespace

import pytest

import utils.llms as llm_module


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 30.0),
        ("1", 5.0),
        ("30", 30.0),
        ("600", 120.0),
        ("bad", 30.0),
    ],
)
def test_openai_request_timeout_is_bounded(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("OPENAI_REQUEST_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", value)
    assert llm_module._timeout_seconds() == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 2),
        ("-1", 0),
        ("3", 3),
        ("99", 5),
        ("bad", 2),
    ],
)
def test_openai_retries_are_bounded(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)
    else:
        monkeypatch.setenv("OPENAI_MAX_RETRIES", value)
    assert llm_module._max_retries() == expected


def test_model_configuration_passes_bounded_settings(monkeypatch):
    calls = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(llm_module, "OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "4")
    monkeypatch.setitem(sys.modules, "langchain_openai", SimpleNamespace(ChatOpenAI=FakeChatOpenAI))

    instance = llm_module.LLMModel()
    assert instance.model_name == "test-model"
    assert calls == [{"model": "test-model", "timeout": 20.0, "max_retries": 4}]


def test_model_fails_explicitly_when_api_key_is_missing(monkeypatch):
    monkeypatch.setattr(llm_module, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
        llm_module.LLMModel()
