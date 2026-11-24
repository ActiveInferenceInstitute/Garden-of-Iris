"""Tests for hindsight: chunking, the stubbed summary call, and CLI usage."""

import hashlib
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import hindsight
import iris_llm


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


def _thoughts(texts=("Synthetic private sentinel",), dates=None):
    if dates is None:
        dates = ["2024-01-02"] * len(texts)
    return pd.DataFrame({
        "Post date": pd.to_datetime(dates).tz_localize("US/Pacific"),
        "Thought": texts, "Platform": ["fourthought"] * len(texts),
        "Positive": [1] * len(texts), "Negative": [0] * len(texts),
        "Privacy": [0] * len(texts), "Truth": [50] * len(texts),
        "Type": ["STATEMENT"] * len(texts),
    })


def _summarizer(monkeypatch):
    calls = []

    def chat(messages, model, **params):
        calls.append({"messages": json.loads(json.dumps(messages)), "model": model, **params})
        return f"Synthetic summary {len(calls)}"

    monkeypatch.setattr(iris_llm, "chat", chat)
    return calls


@pytest.mark.parametrize("value", ["", "  ", None])
def test_no_text_request_never_reaches_provider(monkeypatch, value):
    monkeypatch.setattr(iris_llm, "chat", lambda *a, **k: pytest.fail("empty request"))
    with pytest.raises(ValueError):
        hindsight.create_summary([{"role": "user", "content": value}])
    assert hindsight.split_text_into_chunks("") == []


def test_timeout_retry_budget_is_finite_and_does_not_fabricate_text(monkeypatch):
    class Timeout(Exception):
        pass

    calls, sleeps = [], []

    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise Timeout("synthetic timeout")

    monkeypatch.setattr(iris_llm, "APITimeoutError", Timeout)
    monkeypatch.setattr(iris_llm, "chat", timeout)
    monkeypatch.setattr(hindsight.time, "sleep", sleeps.append)
    with pytest.raises(hindsight.SummaryRequestError, match="exhausted 3"):
        hindsight.create_summary([{"role": "user", "content": "text"}], timeout=7, retry_delay=2)
    assert len(calls) == 3
    assert sleeps == [2, 2]
    assert all(call["timeout"] == 7 for call in calls)


def test_rate_limit_exhaustion_never_publishes_a_success_cache(tmp_path, monkeypatch):
    class RateLimited(Exception):
        pass

    monkeypatch.chdir(tmp_path)
    calls, sleeps = [], []

    def limited(*args, **kwargs):
        calls.append(kwargs)
        raise RateLimited("synthetic rate limit")

    monkeypatch.setattr(iris_llm, "RateLimitError", RateLimited)
    monkeypatch.setattr(iris_llm, "chat", limited)
    monkeypatch.setattr(hindsight.time, "sleep", sleeps.append)
    with pytest.raises(hindsight.SummaryRequestError) as raised:
        hindsight.create_daily_summaries(_thoughts())
    assert isinstance(raised.value.__cause__, RateLimited)
    assert len(calls) == 3
    assert sleeps == [5, 5]
    assert all(call["timeout"] == 60 for call in calls)
    assert not Path("daily_summaries.csv").exists()


def test_transient_rate_limit_publishes_only_the_recovered_summary(tmp_path, monkeypatch):
    class RateLimited(Exception):
        pass

    monkeypatch.chdir(tmp_path)
    calls, sleeps = [], []

    def recover(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RateLimited("synthetic rate limit")
        return "Recovered summary"

    monkeypatch.setattr(iris_llm, "RateLimitError", RateLimited)
    monkeypatch.setattr(iris_llm, "chat", recover)
    monkeypatch.setattr(hindsight.time, "sleep", sleeps.append)
    hindsight.create_daily_summaries(_thoughts())
    assert len(calls) == 2
    assert sleeps == [5]
    assert pd.read_csv("daily_summaries.csv")["Summary"].tolist() == ["Recovered summary"]


@pytest.mark.parametrize("change", ["text", "model", "policy", "program"])
def test_daily_cache_reuses_only_matching_content_and_configuration(tmp_path, monkeypatch, change):
    monkeypatch.chdir(tmp_path)
    calls = _summarizer(monkeypatch)
    frame = _thoughts()
    hindsight.create_daily_summaries(frame)
    first = Path("daily_summaries.csv").read_bytes()
    hindsight.create_daily_summaries(frame)
    assert len(calls) == 1
    assert Path("daily_summaries.csv").read_bytes() == first
    if change == "text":
        frame.loc[0, "Thought"] = "Edited synthetic thought"
    elif change == "model":
        monkeypatch.setattr(hindsight, "SUMMARY_MODEL", "synthetic/changed-model")
    elif change == "policy":
        monkeypatch.setattr(hindsight, "CACHE_POLICY", {**hindsight.CACHE_POLICY, "fixture": "changed"})
    else:
        monkeypatch.setattr(hindsight, "_file_digest", lambda path: "a" * 64)
    hindsight.create_daily_summaries(frame)
    assert len(calls) == 2
    assert pd.read_csv("daily_summaries.csv")["Summary"].tolist() == ["Synthetic summary 2"]


def test_cache_records_actual_dynamic_prompt_without_copying_raw_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = _summarizer(monkeypatch)
    hindsight.create_daily_summaries(_thoughts())
    context = json.loads(pd.read_csv("daily_summaries.csv").iloc[0]["Context"])
    wire = calls[0]["messages"]
    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert context["requests"][0]["input_sha256"] == hashlib.sha256(encoded.encode()).hexdigest()
    assert any(context["prompt_time"] in message["content"] for message in wire)
    assert "Synthetic private sentinel" not in json.dumps(context)


def test_legacy_and_tampered_cache_are_rejected_without_rewriting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = _summarizer(monkeypatch)
    path = Path("daily_summaries.csv")
    path.write_text("Date,Summary\n2024-01-02,Historical summary\n", encoding="utf-8")
    historical = path.read_bytes()
    with pytest.raises(hindsight.SummaryCacheError, match="unbound"):
        hindsight.create_daily_summaries(_thoughts())
    assert path.read_bytes() == historical
    assert not calls
    path.unlink()
    hindsight.create_daily_summaries(_thoughts())
    frame = pd.read_csv(path)
    frame.loc[0, "Summary"] = "Tampered output"
    frame.to_csv(path, index=False)
    tampered = path.read_bytes()
    with pytest.raises(hindsight.SummaryCacheError, match="binding"):
        hindsight.create_weekly_summaries()
    assert path.read_bytes() == tampered
    assert len(calls) == 1


def test_upstream_changes_propagate_and_removed_periods_leave_no_stale_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = _summarizer(monkeypatch)
    frame = _thoughts()
    hindsight.create_daily_summaries(frame)
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()
    assert len(calls) == 3
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()
    assert len(calls) == 3
    frame.loc[0, "Thought"] = "An edited thought"
    hindsight.create_daily_summaries(frame)
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()
    assert len(calls) == 6
    hindsight.create_daily_summaries(frame.iloc[:0])
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()
    hindsight.create_seasonal_summaries()
    assert len(calls) == 6
    for filename in ("daily_summaries.csv", "weekly_summaries.csv", "monthly_summaries.csv"):
        assert pd.read_csv(filename).empty


def test_empty_stages_and_missing_text_do_not_make_model_requests(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(iris_llm, "chat", lambda *a, **k: pytest.fail("empty-stage request"))
    hindsight.create_daily_summaries(_thoughts(("", "  ", None), ["2024-01-01"] * 3))
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()
    hindsight.create_seasonal_summaries()
    assert pd.read_csv("daily_summaries.csv").empty


def test_model_failure_never_creates_a_success_cache_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fail(*args, **kwargs):
        raise iris_llm.ModelOutputError("No usable model text")

    monkeypatch.setattr(iris_llm, "chat", fail)
    with pytest.raises(iris_llm.ModelOutputError):
        hindsight.create_daily_summaries(_thoughts())
    assert not Path("daily_summaries.csv").exists()


def test_seeded_augmentation_is_local_reproducible_and_year_qualified(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _summarizer(monkeypatch)
    hindsight.create_daily_summaries(_thoughts(
        ("First year", "Second year"), ["2023-01-02", "2024-01-02"]
    ))
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()
    stages = [
        (hindsight.construct_daily_training_data, "temporal_iris.csv"),
        (hindsight.construct_weekly_training_data, "weekly_iris.csv"),
        (hindsight.construct_monthly_training_data, "monthly_iris.csv"),
    ]
    state = random.getstate()
    for construct, filename in stages:
        first = construct(seed=19)
        before = Path(filename).read_bytes()
        receipt = Path(filename + ".provenance.json").read_bytes()
        assert construct(seed=19) == first
        assert Path(filename).read_bytes() == before
        assert Path(filename + ".provenance.json").read_bytes() == receipt
        metadata = json.loads(receipt)
        assert metadata["output_sha256"] == hashlib.sha256(before).hexdigest()
    assert random.getstate() == state


@pytest.mark.parametrize("name", [
    "construct_daily_training_data", "construct_weekly_training_data",
    "construct_monthly_training_data",
])
def test_every_template_choice_keeps_two_years_distinct(tmp_path, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    _summarizer(monkeypatch)
    hindsight.create_daily_summaries(_thoughts(("first", "second"), ["2023-01-02", "2024-01-02"]))
    hindsight.create_weekly_summaries()
    hindsight.create_monthly_summaries()

    class CyclingChoices:
        def __init__(self, seed):
            self.index = seed

        def choice(self, values):
            value = values[self.index % len(values)]
            self.index += 1
            return value

    monkeypatch.setattr(hindsight, "random", SimpleNamespace(Random=CyclingChoices))
    for seed in range(20):
        pairs = getattr(hindsight, name)(seed=seed)
        assert "2023" in pairs[0][0]
        assert "2024" in pairs[-1][0]
        assert pairs[0][0] != pairs[-1][0]


@pytest.mark.parametrize("defect", ["missing_clock", "wrong_stage", "invalid_source_digest"])
def test_consumer_rejects_incomplete_context_even_with_matching_checksum(tmp_path, monkeypatch, defect):
    monkeypatch.chdir(tmp_path)
    calls = _summarizer(monkeypatch)
    hindsight.create_daily_summaries(_thoughts())
    path = Path("daily_summaries.csv")
    frame = pd.read_csv(path)
    context = json.loads(frame.loc[0, "Context"])
    if defect == "missing_clock":
        context["prompt_time"] = None
    elif defect == "wrong_stage":
        context["stage"] = "weekly"
    else:
        context["source_sha256"] = "not-a-digest"
    encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    frame.loc[0, "Binding"] = hashlib.sha256(encoded.encode()).hexdigest()
    frame.loc[0, "Context"] = json.dumps(context, sort_keys=True, ensure_ascii=False)
    frame.to_csv(path, index=False)
    before = path.read_bytes()
    with pytest.raises(hindsight.SummaryCacheError, match="binding"):
        hindsight.create_weekly_summaries()
    assert len(calls) == 1
    assert path.read_bytes() == before
    assert not Path("weekly_summaries.csv").exists()
