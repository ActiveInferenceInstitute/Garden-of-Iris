"""Tests for parse_fourthought: cleaning, chunking, classification, and the
chunk-by-chunk model loop (with a stubbed model call)."""

import types

import pytest

import iris_llm
import parse_fourthought


def test_clean_text_single_line_and_recased():
    assert parse_fourthought.clean_text("HELLO WORLD. BYE NOW") == "Hello world. Bye now"


def test_clean_text_replaces_newlines():
    assert parse_fourthought.clean_text("A\nB") == "A b"


def test_chunk_text_splits_at_limit():
    chunks = parse_fourthought.chunk_text("abcdef", max_chunk_length=4)
    assert chunks == ["abcd", "ef"]


def test_chunk_text_default_limit_is_3000():
    assert len(parse_fourthought.chunk_text("x" * 9000)) == 3


def test_classify_claim_matches_expected_format():
    assert parse_fourthought.classify_claim(
        "The world will continue on well past 2042, PREDICTION"
    ) == ("The world will continue on well past 2042", "PREDICTION")


def test_classify_claim_pattern_is_uppercase_only():
    # The pipeline's pattern expects the upper-case type the prompt requests.
    assert parse_fourthought.classify_claim("Where did I leave my keys?, question") is None


def test_classify_claim_rejects_other_lines():
    assert parse_fourthought.classify_claim("no type here") is None


def _stub_chat_completion(calls, responses):
    def _call(messages, model, **params):
        calls.append({"messages": messages, "model": model, "params": params})
        contents = responses.pop(0)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=c)) for c in contents]
        )

    return _call


def test_parse_thoughts_collects_lines_from_every_choice(monkeypatch):
    calls = []
    responses = [
        ["A statement, STATEMENT", "A prediction, PREDICTION"],
        ["A question?, QUESTION"],
    ]
    monkeypatch.setattr(iris_llm, "chat_completion", _stub_chat_completion(calls, responses))

    claims = parse_fourthought.parse_thoughts("x" * 4000)

    assert claims == ["A statement, STATEMENT", "A prediction, PREDICTION", "A question?, QUESTION"]
    assert len(calls) == 2
    # Every request replays the dialectic explanation and the last messages.
    for call in calls:
        assert call["messages"][0]["content"] == parse_fourthought.EXPLANATION
        assert call["messages"][1]["content"] == parse_fourthought.ASSISTANT_ACK
    assert calls[0]["model"] == parse_fourthought.models["thought_type"]


def test_parse_thoughts_uses_requested_model(monkeypatch):
    calls = []
    monkeypatch.setattr(iris_llm, "chat_completion", _stub_chat_completion(calls, [["x, STATEMENT"]]))
    parse_fourthought.parse_thoughts("text", model="custom/model")
    assert calls[0]["model"] == "custom/model"


def test_main_requires_exactly_one_argument(capsys):
    assert parse_fourthought.main([]) == 2
    assert parse_fourthought.main(["a", "b"]) == 2


def test_main_rejects_unsupported_input():
    assert parse_fourthought.main(["notes.txt"]) == 1


def test_main_prints_classified_thoughts(monkeypatch, capsys):
    monkeypatch.setattr(parse_fourthought, "extract_text_from_pdf", lambda path: "Some text.")
    monkeypatch.setattr(
        parse_fourthought, "parse_thoughts", lambda text, model=None: ["A prediction, PREDICTION", "junk"]
    )
    assert parse_fourthought.main(["paper.pdf"]) == 0
    out = capsys.readouterr().out
    assert "A prediction" in out
    assert "PREDICTION" in out
    assert "junk" not in out
