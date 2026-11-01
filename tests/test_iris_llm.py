"""Tests for iris_llm: client construction, request shapes, and helpers.

A stub ``openai`` module replaces the SDK, so no network access or API key is
needed.
"""

import types

import pytest

import iris_llm


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, contents):
        self.choices = [_Choice(c) for c in contents]


class _FakeCompletions:
    def __init__(self, calls, contents):
        self._calls = calls
        self._contents = contents

    def create(self, **kwargs):
        self._calls.append(kwargs)
        return _Response(self._contents)


class _FakeClient:
    def __init__(self, calls, contents, **kwargs):
        self.init_kwargs = kwargs
        self.chat = types.SimpleNamespace(
            completions=_FakeCompletions(calls, contents)
        )


class _FakeOpenAI:
    def __init__(self, calls, contents=(" first choice  ", "second choice")):
        self._calls = calls
        self._contents = contents
        self.client = None

    def OpenAI(self, **kwargs):
        self.client = _FakeClient(self._calls, self._contents, **kwargs)
        return self.client


@pytest.fixture
def fake_sdk(monkeypatch):
    calls = []
    fake = _FakeOpenAI(calls)
    monkeypatch.setattr(iris_llm, "openai", fake)
    monkeypatch.setattr(iris_llm, "_client", None)
    return fake, calls


def test_chat_returns_first_choice_text(fake_sdk):
    _, calls = fake_sdk
    assert iris_llm.chat([{"role": "user", "content": "hi"}], model="m") == "first choice"
    assert calls == [{"model": "m", "messages": [{"role": "user", "content": "hi"}]}]


def test_chat_forwards_params(fake_sdk):
    _, calls = fake_sdk
    iris_llm.chat([{"role": "user", "content": "hi"}], model="m", temperature=0.5, stop=["END"])
    assert calls[0]["temperature"] == 0.5
    assert calls[0]["stop"] == ["END"]


def test_complete_wraps_prompt_as_user_message(fake_sdk):
    _, calls = fake_sdk
    iris_llm.complete("hello", model="m", max_tokens=222)
    assert calls[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert calls[0]["max_tokens"] == 222


def test_complete_joins_prompt_lists(fake_sdk):
    _, calls = fake_sdk
    iris_llm.complete(["a", "b"], model="m")
    assert calls[0]["messages"] == [{"role": "user", "content": "a\nb"}]


def test_chat_completion_returns_raw_response(fake_sdk):
    response = iris_llm.chat_completion([{"role": "user", "content": "hi"}], model="m")
    assert [choice.message.content for choice in response.choices] == [
        " first choice  ",
        "second choice",
    ]


def test_client_uses_openrouter_base_url_and_headers(fake_sdk, monkeypatch):
    fake, _ = fake_sdk
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    iris_llm.chat([{"role": "user", "content": "hi"}], model="m")
    assert fake.client.init_kwargs["base_url"] == iris_llm.OPENROUTER_BASE_URL
    assert fake.client.init_kwargs["api_key"] == "or-key"
    headers = fake.client.init_kwargs["default_headers"]
    assert headers["HTTP-Referer"] == iris_llm.OPENROUTER_REFERER
    assert headers["X-OpenRouter-Title"] == iris_llm.OPENROUTER_TITLE


def test_api_key_falls_back_to_openai_key(fake_sdk, monkeypatch):
    fake, _ = fake_sdk
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    iris_llm.chat([{"role": "user", "content": "hi"}], model="m")
    assert fake.client.init_kwargs["api_key"] == "fallback-key"


def test_client_is_created_once(fake_sdk):
    fake, _ = fake_sdk
    iris_llm.chat([{"role": "user", "content": "one"}], model="m")
    first = fake.client
    iris_llm.chat([{"role": "user", "content": "two"}], model="m")
    assert fake.client is first


def test_retry_exceptions_are_exported():
    assert issubclass(iris_llm.RateLimitError, Exception)
    assert issubclass(iris_llm.APITimeoutError, Exception)
