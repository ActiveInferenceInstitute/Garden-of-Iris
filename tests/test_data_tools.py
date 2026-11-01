"""Tests for the data tools: text_process and twitter_archive."""

import csv
import sys
import types

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
