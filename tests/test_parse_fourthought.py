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
    examples = [
        line
        for paragraph in parse_fourthought.EXPLANATION.split("\n\n")
        if "\n" in paragraph
        for line in paragraph.splitlines()
        if line.strip()
    ]
    assert examples
    for example in examples:
        thought, separator, kind = example.rpartition(",")
        assert separator and thought.strip()
        assert kind.strip() in {"PREDICTION", "REFLECTION", "STATEMENT", "QUESTION"}
        assert parse_fourthought.classify_claim(example) == (thought.strip(), kind.strip())


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


@pytest.mark.parametrize("text", ["", " \n ", "Sentence. "])
def test_empty_segments_are_safe_and_empty_input_never_calls_model(monkeypatch, text):
    calls = []
    monkeypatch.setattr(iris_llm, "chat_completion", _stub_chat_completion(calls, [["Done, STATEMENT"]]))
    cleaned = parse_fourthought.clean_text(text)
    lines = parse_fourthought.parse_thoughts(cleaned)
    if cleaned:
        assert lines == ["Done, STATEMENT"]
        assert calls
    else:
        assert lines == []
        assert not calls


def test_empty_extraction_is_a_cli_failure_before_provider(monkeypatch, capsys):
    monkeypatch.setattr(parse_fourthought, "extract_text_from_pdf", lambda path: "")
    monkeypatch.setattr(iris_llm, "chat_completion", lambda *a, **k: pytest.fail("empty provider request"))
    assert parse_fourthought.main(["image-only.pdf"]) == 1
    assert "No extractable text" in capsys.readouterr().err


def test_all_invalid_classifications_fail_but_partial_results_remain_visible(monkeypatch, capsys):
    monkeypatch.setattr(parse_fourthought, "extract_text_from_pdf", lambda path: "Text")
    monkeypatch.setattr(parse_fourthought, "parse_thoughts", lambda text: ["junk", "also junk"])
    assert parse_fourthought.main(["paper.pdf"]) == 1
    captured = capsys.readouterr()
    assert "Rejected 2" in captured.err
    assert "No valid classifications" in captured.err
    monkeypatch.setattr(parse_fourthought, "parse_thoughts", lambda text: ["A thought, STATEMENT", "junk"])
    assert parse_fourthought.main(["paper.pdf"]) == 0
    captured = capsys.readouterr()
    assert "A thought" in captured.out
    assert "Rejected 1" in captured.err




def test_nullable_raw_response_uses_canonical_error(monkeypatch):
    monkeypatch.setattr(iris_llm, "chat_completion", _stub_chat_completion([], [[None]]))
    with pytest.raises(iris_llm.ModelOutputError):
        parse_fourthought.parse_thoughts("text")


@pytest.mark.parametrize("line", [", QUESTION", "   , STATEMENT"])
def test_empty_thought_is_rejected(line):
    assert parse_fourthought.classify_claim(line) is None
