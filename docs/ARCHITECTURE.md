# Architecture

This document describes every component in the repository, what it does, how
the pieces fit together, and which parts are runnable today. It is grounded in
the source code; where a script is unfinished or relies on files that are not
in the repository, that is stated explicitly.

## Overview

The repository is a loose collection of experimental tools built around one
idea: **Iris**, a language model trained on community contributions and
organized by the **FourThought dialectic**. The components form an informal
pipeline:

```
                     +---------------------------+
                     |   sources of raw thought  |
                     +---------------------------+
                       |                      |
       Twitter archive                 FourThought dump
       (data/tweets.js)                (prophet_thought_dump_ALL_THOUGHTS_2023.csv)
                       |                      |
                       v                      v
              twitter_archive.py        parse_fourthought.py
              (twitter_archive.csv)     (web/PDF -> thought types)
                       |                      |
                       +----------+-----------+
                                  |
                                  v
                        +------------------+
                        |   hindsight.py  |
                        |  summarization  |
                        +------------------+
                          |          |
                          v          v
                   summaries    training data
                   (daily/      (temporal_iris.csv,
                    weekly/      weekly_iris.csv,
                    monthly/     monthly_iris.csv)
                    seasonal)
                                  |
                                  v
                     +---------------------------+
                     |      iris_apparently.py   |
                     |  "DemocraticLLM" (sketch) |
                     +---------------------------+
                                  |
                                  v
                     +---------------------------+
                     |      discord_bot.py       |
                     |  Iris the Discord oracle  |
                     +---------------------------+
```

The only tracked training data in the repository are
[`data/semantic-iris.csv`](DATA.md#datasemantic-iriscsv) and
[`data/chat-iris.csv`](DATA.md#datachat-iriscsv); the inputs consumed by
`hindsight.py` and `twitter_archive.py` are personal archives that are
deliberately **not** committed.

## The FourThought dialectic

FourThought classifies every thought by temporal focus and certainty, and is
referenced throughout `hindsight.py`, `parse_fourthought.py`, and
`discord_bot.py`:

- **Predictions** — claims about the future. They cannot be verified
  immediately; time must pass.
- **Reflections** — claims about the past. They can be verified against a
  record.
- **Statements** — claims about the present. They can be verified through a
  democratic process of asking the community.
- **Questions** — queries born of uncertainty, not declarations of truth.

Each thought also carries two voting dimensions in the FourThought data:
*truth* (certainty, 0–100) and *good* (valence/sentiment).

## Components

### `discord_bot.py` — the Iris Discord bot

A Discord bot (`commands.Bot`, prefix `/`) named Iris that acts as an "oracle
and time compass": it summarizes community threads, answers questions, pulls
tarot cards, and relays fine-tuned-model responses. Requires
`DISCORD_BOT_KEY`, `OPENAI_API_KEY`, and `AIRTABLE_API_KEY`.

**Channel pools.** Three channels are monitored in `on_message`; any new
non-command message triggers an automatic GPT-4 summary of the recent thread:

| Pool | Channel ID | Behavior |
| --- | --- | --- |
| `fourthought_pool` | `1090373822454182090` | Weaves the FourThought thread into a narrative ("time compass"), ≤ 250 words |
| `question_pool` | `1086437563654475846` | Summarizes what the community is uncertain about; never answers |
| `prophecy_pool` | `1083409321754378290` | Integrates the "arrow of time" of predictions, ≤ 300 words |

Each pool reads up to 50 messages of history, ignores slash commands, builds a
chat conversation, and sends the response (chunked at 2000 characters).

**DM relay (`frankeniris`).** Private messages are answered by a
"Frankeniris" relay: a fine-tuned `chat-iris` completion is folded into a
GPT-3.5-turbo conversation along with recent channel history, truncated to a
20,000-character budget.

**Slash commands.**

| Command | Aliases | What it does |
| --- | --- | --- |
| `/channel` | `/c` | Channels wisdom: feeds a random question from `data/chat-iris.csv` into Frankeniris |
| `/faq` | — | Answers a random question from `data/chat-iris.csv` with its stored completion |
| `/infuse` | `/in`, `/inject` | Scrapes a URL (headless Selenium), chunks the text, and summarizes each chunk with GPT-4 into the stream |
| `/iris` | `/ask` | Queries the fine-tuned `chat-iris` model directly |
| `/davinci` | — | Queries `text-davinci-002` (tester-gated) |
| `/claim` | — | Logs an attestation into `iris_training-data.csv` |
| `/pullcard` | — | Draws a card from the Iris tarot deck (Airtable, falling back to `tarot_text.csv`); interprets it with `text-davinci-002` when an intention is given |
| `/ask_group` | — | DMs the "Birdies" role a question, collects answers via modals, and pools them into a consensus |

**Training-data collection.** `load_training_data()` reads
`iris_training-data.csv` (columns `prompt,completion,speaker`), creating it on
first run. `/ask` saves clarification feedback and `/claim` saves attestations
as new rows.

### `hindsight.py` — hindsight summarization pipeline

Turns a personal archive of tagged thoughts (FourThought data + Twitter) into
period summaries and fine-tuning data. Requires `OPENAI_API_KEY`.

**Inputs** (not committed to the repository):

- `prophet_thought_dump_ALL_THOUGHTS_2023.csv` — FourThought export. Columns
  consumed: `Post date` (format `%m/%d/%y %I:%M %p`, timezone US/Pacific),
  `Good` (a two-line cell of the form `+N` / `-M`, split into `Positive` /
  `Negative`), `Thought`, `Privacy`, `Truth`, `Type`. See
  [DATA.md](DATA.md#prophet_thought_dump_all_thoughts_2023csv-schema).
- `twitter_archive.csv` — produced by `twitter_archive.py`. Columns
  `created_at`, `full_text`, `retweet_count`, `favorite_count` (the `lang`
  column is dropped).

The module-level block loads both sources, tags them `Platform` =
`fourthought` / `twitter`, concatenates, and sorts by `Post date`. It currently
executes `construct_monthly_training_data()`; the summarization functions are
commented out there.

**Summarization functions** (all GPT-4 via `create_summary`, with
rate-limit retry and caching):

| Function | Output file | Granularity |
| --- | --- | --- |
| `create_daily_summaries` | `daily_summaries.csv` (`Date`, `Summary`) | Per day |
| `create_weekly_summaries` | `weekly_summaries.csv` (`Week_Start_Date`, `Summary`) | Resampled Monday weeks |
| `create_monthly_summaries` | `monthly_summaries.csv` (`Month_Year`, `Summary`) | Per month |
| `create_seasonal_summaries` | prints only | Winter/Spring/Summer/Fall |

Long inputs are chunked (`split_text_into_chunks`, ~4000 chars) and
recursively summarized before stitching.

**Training-data construction** (prompt randomization over question templates
and date formats):

| Function | Output file | Columns |
| --- | --- | --- |
| `construct_daily_training_data` | `temporal_iris.csv` | `Prompt`, `Completion` |
| `construct_weekly_training_data` | `weekly_iris.csv` | `Prompt`, `Completion` |
| `construct_monthly_training_data` | `monthly_iris.csv` | `Prompt`, `Completion` |

**Stubs.** The following functions are declared with `pass` bodies and
describe planned work: `create_yearly_summaries`, `create_certainty_summaries`,
`create_sentiment_summaries`, `create_temporal_focus_summaries`,
`create_trend_analysis`, `create_periodic_reflections`,
`create_predictions_review`, `create_trackable_summaries`.

### `parse_fourthought.py` — FourThought parser CLI

Command-line tool that parses noisy scraped text into the four thought types:

```bash
python parse_fourthought.py http://example.com      # URL (headless Selenium)
python parse_fourthought.py /path/to/paper.pdf      # PDF (PyPDF2)
```

The text is cleaned (newlines to spaces, sentence re-casing), split into
3000-character chunks, and sent to GPT-3.5-turbo with a system prompt
describing the FourThought dialectic and the exact output format
`THOUGHT_TEXT, THOUGHT_TYPE`. Matches are printed as thought text and type
separately. Requires `OPENAI_API_KEY`. The module also defines a `models` dict
of fine-tuned model IDs (`semantic`, `davinci`, `thought_type`) that are
referenced by the dialectic prompts but not used in the main flow.

### `twitter_archive.py` — Twitter archive converter

Reads `data/tweets.js` (a Twitter archive export; the JSON array is located
between the first `[` and last `]`), extracts
`id, created_at, full_text, retweet_count, favorite_count, lang`, and writes
`twitter_archive.csv`. Depends on `pandas`. The `data/tweets.js` input is a
personal archive and is **not** committed.

### `text_process.py` — sentence-pair builder

Reads a local text file named `ceresonepage`, sentence-tokenizes it with NLTK,
and pairs each sentence with its successor to produce
`ceresonepage.csv` with columns `prompt,completion` — a simple
fine-tuning-data construction for "next sentence" generation. The input file
name is hardcoded.

### `iris_apparently.py` — "DemocraticLLM" sketch (not runnable)

An unfinished TensorFlow/Keras attempt at an Iris architecture: a Transformer
encoder–decoder (`DemocraticLLM`) whose encoder and decoder layers add extra
attention blocks over *source embeddings*, plus sinusoidal *temporal
embeddings* computed from timestamps (seconds→year components). The intended
training CSV schema is `text, source_id, timestamp`.

It is a **non-runnable sketch**. Known blockers, verified against the source:

1. `layers` is referenced (`MultiHeadAttention(layers.Layer)`) but never
   imported.
2. Module-level statements call `create_sinusoidal_embeddings(...)` (line 56)
   and `DemocraticLLM(...)` (line 79) before those names are defined, which
   raises `NameError` at import time.
3. The `model.fit(x=[...], ...)` call does not match the required positional
   arguments of `DemocraticLLM.call(...)`.
4. `create_source_embeddings` and `create_temporal_embeddings` are defined but
   never used.

Fixing these is out of scope for a documentation pass; see
[TO-DO.md](../TO-DO.md) for the deferred item.

## Environment variables

| Variable | Required by | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | `discord_bot.py`, `hindsight.py`, `parse_fourthought.py` | OpenAI API access |
| `DISCORD_BOT_KEY` | `discord_bot.py` | Discord bot token |
| `AIRTABLE_API_KEY` | `discord_bot.py` | Airtable tarot-deck lookup |

A template is provided in [.env.example](../.env.example).

## Caveats

- All OpenAI calls use the legacy API surface (`openai.Completion`,
  `openai.ChatCompletion`) from the pre-1.0 `openai` package; the code will
  not run against `openai >= 1.0` without changes.
- The fine-tuned model IDs in `discord_bot.py` and `parse_fourthought.py`
  (`davinci:ft-personal:*`) refer to retired models and are not valid today.
- Discord channel IDs are hardcoded; the bot only behaves as documented when
  run in the original server layout.
