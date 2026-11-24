"""Tests for the data tools: text_process and twitter_archive."""

import csv
import json
import sys
import types

import pandas as pd

import hindsight
import text_process
import twitter_archive


def _stub_nltk(monkeypatch):
    def sent_tokenize(paragraph):
        return [s for s in paragraph.split('. ') if s]

    fake = types.SimpleNamespace(tokenize=types.SimpleNamespace(sent_tokenize=sent_tokenize))
    monkeypatch.setitem(sys.modules, "nltk", fake)


def test_sentence_pairs_pairs_consecutive_sentences(monkeypatch):
    _stub_nltk(monkeypatch)
    pairs = text_process.sentence_pairs("One. Two. Three")
    assert pairs == [
        {"prompt": "One", "completion": "Two"},
        {"prompt": "Two", "completion": "Three"},
    ]


def test_text_process_main_writes_csv(monkeypatch, tmp_path):
    _stub_nltk(monkeypatch)
    source = tmp_path / "source.txt"
    source.write_text("Alpha. Beta", encoding="utf-8")
    output = tmp_path / "pairs.csv"

    assert text_process.main([str(source), str(output)]) == 0
    with open(output, encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows == [["prompt", "completion"], ["Alpha", "Beta"]]


def test_load_tweets_reads_the_json_array(tmp_path):
    archive = tmp_path / "tweets.js"
    archive.write_text(
        'window.YTD.tweets.part0 = [{"tweet": {"id": "1", "created_at": "x",'
        ' "full_text": "hello", "retweet_count": "0", "favorite_count": "1",'
        ' "lang": "en"}}]',
        encoding="utf-8",
    )
    tweets = twitter_archive.load_tweets(archive)
    assert tweets[0]["tweet"]["full_text"] == "hello"
    rows = twitter_archive.tweets_to_rows(tweets)
    assert rows == [
        {
            "id": "1",
            "created_at": "x",
            "full_text": "hello",
            "retweet_count": "0",
            "favorite_count": "1",
            "lang": "en",
        }
    ]


def test_twitter_archive_main_writes_csv(tmp_path):
    archive = tmp_path / "tweets.js"
    archive.write_text(
        'window.YTD.tweets.part0 = [{"tweet": {"id": "1", "created_at": "x",'
        ' "full_text": "hello", "retweet_count": "0", "favorite_count": "1",'
        ' "lang": "en"}}]',
        encoding="utf-8",
    )
    output = tmp_path / "twitter_archive.csv"

    assert twitter_archive.main([str(archive), str(output)]) == 0
    assert output.read_text(encoding="utf-8").splitlines()[0].split(",") == [
        "id",
        "created_at",
        "full_text",
        "retweet_count",
        "favorite_count",
        "lang",
    ]


def test_twitter_archive_main_reports_missing_file(tmp_path, capsys):
    assert twitter_archive.main([str(tmp_path / "absent.js"), str(tmp_path / "out.csv")]) == 1
    assert "Error reading" in capsys.readouterr().out


def test_empty_archive_has_schema_and_is_consumed_by_hindsight(tmp_path):
    archive = tmp_path / "tweets.js"
    archive.write_text("window.YTD.tweets.part0 = []", encoding="utf-8")
    output = tmp_path / "twitter.csv"
    assert twitter_archive.main([str(archive), str(output)]) == 0
    assert output.read_text(encoding="utf-8").strip() == ",".join(twitter_archive.FIELDS)
    thoughts = tmp_path / "thoughts.csv"
    pd.DataFrame([{
        "Post date": "01/02/24 03:00 PM", "Good": "+1\n-0",
        "Thought": "Synthetic thought", "Privacy": 0, "Truth": 50, "Type": "STATEMENT",
    }]).to_csv(thoughts, index=False)
    merged = hindsight.load_merged_data(thoughts, output)
    assert merged["Thought"].tolist() == ["Synthetic thought"]
    assert str(merged["Post date"].dt.tz) == "US/Pacific"
    assert str(merged["retweet_count"].dtype) == "Int64"


def test_archive_stdout_does_not_expose_selected_or_extra_record_text(tmp_path, capsys):
    tweet = {
        "id": "1", "created_at": "Tue Jan 02 23:00:00 +0000 2024",
        "full_text": "PRIVATE_SELECTED_SENTINEL", "retweet_count": "0",
        "favorite_count": "1", "lang": "en", "extra": "PRIVATE_EXTRA_SENTINEL",
    }
    source = tmp_path / "tweets.js"
    source.write_text("window.YTD.tweets.part0 = " + json.dumps([{"tweet": tweet}]), encoding="utf-8")
    output = tmp_path / "tweets.csv"
    assert twitter_archive.main([str(source), str(output)]) == 0
    captured = capsys.readouterr().out
    assert "PRIVATE_SELECTED_SENTINEL" not in captured
    assert "PRIVATE_EXTRA_SENTINEL" not in captured
    frame = pd.read_csv(output)
    assert list(frame.columns) == list(twitter_archive.FIELDS)
    assert frame["full_text"].tolist() == ["PRIVATE_SELECTED_SENTINEL"]
