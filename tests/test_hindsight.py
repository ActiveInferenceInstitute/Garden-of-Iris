"""Tests for hindsight: chunking, the stubbed summary call, and CLI usage."""

import iris_llm
import hindsight


def test_split_text_into_chunks_balances_chunks():
    # 10 chars, max 4 -> 3 chunks of 4/4/2 (evenly redistributed).
    assert hindsight.split_text_into_chunks("a" * 10, max_chunk_size=4) == [
        "aaaa",
        "aaaa",
        "aa",
    ]


def test_split_text_into_chunks_short_text():
    assert hindsight.split_text_into_chunks("abc", max_chunk_size=4000) == ["abc"]


def test_create_summary_uses_chat_client(monkeypatch):
    calls = []

    def _chat(messages, model, **params):
        calls.append({"messages": messages, "model": model})
        return "a summary"

    monkeypatch.setattr(iris_llm, "chat", _chat)
    conversation = [{"role": "user", "content": "thoughts"}]
    assert hindsight.create_summary(conversation) == "a summary"
    assert calls[0]["messages"] == conversation
    assert calls[0]["model"] == "openai/gpt-4o-mini"


def test_main_without_flags_prints_usage(capsys):
    hindsight.main([])
    assert "usage:" in capsys.readouterr().out.lower()
