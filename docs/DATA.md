# Data

This page documents every data file in the repository and every data file the
scripts expect or generate. Column names are exactly as read or written by the
code.

## Tracked data (in the repository)

### data/semantic-iris.csv

Training data for the "semantic" Iris fine-tune. 1,103 data rows (plus a
header). Lines use LF endings; some cells contain embedded newlines.

| Column | Description |
| --- | --- |
| `prompt` | Input text |
| `completion` | Expected continuation/response |

Consumed by `discord_bot.py` indirectly (the `/channel` and `/faq` commands
read `data/chat-iris.csv`, not this file) and referenced historically by the
`models` dictionary in `parse_fourthought.py` (the `semantic` slot, which
pointed at a `semantic-iris-davinci-3` fine-tune, now maps to an OpenRouter
chat model).

### data/chat-iris.csv

Chat training data. 1,502 data rows (plus a header); some cells contain
embedded newlines.

| Column | Description |
| --- | --- |
| `prompt` | A question or prompt |
| `completion` | The expected answer |
| `Source` | Origin label for the pair |

Consumed by `discord_bot.py`: `/channel` picks a random prompt whose text ends
in `?`, `/faq` builds question→completion pairs from matching `prompt` values.

## Inputs expected by scripts (not in the repository)

These are personal archives or generated exports and are deliberately not
committed. `.gitignore` protects them from accidental commits.

| File | Produced by / expected from | Consumed by |
| --- | --- | --- |
| `data/tweets.js` | Twitter archive export | `twitter_archive.py` |
| `prophet_thought_dump_ALL_THOUGHTS_2023.csv` | FourThought export | `hindsight.py` |
| `twitter_archive.csv` | `twitter_archive.py` | `hindsight.py` |
| `tarot_text.csv` | Fallback tarot deck (used if Airtable is unavailable) | `discord_bot.py` (`/pullcard`) |
| `ceresonepage` | Plain-text input file | `text_process.py` |

### prophet_thought_dump_ALL_THOUGHTS_2023.csv — schema

Columns consumed by `hindsight.py`:

| Column | Format | Notes |
| --- | --- | --- |
| `Post date` | `%m/%d/%y %I:%M %p` | Parsed as US/Pacific time |
| `Good` | Two-line cell: `+N` / `-M` | Split into `Positive` / `Negative` vote counts |
| `Thought` | Free text | The thought content |
| `Privacy` | `0` = Public, else Private | Prompt label only; not exclusion, redaction or authorization |
| `Truth` | Numeric | Average certainty, 0–100 |
| `Type` | FourThought type | e.g. `PREDICTION`, `REFLECTION`, `STATEMENT`, `QUESTION` |

## Generated outputs (never committed)

Created by the scripts at the repository root; all are covered by
`.gitignore`:

| File | Created by | Schema |
| --- | --- | --- |
| `twitter_archive.csv` | `twitter_archive.py` | `id, created_at, full_text, retweet_count, favorite_count, lang` |
| `ceresonepage.csv` | `text_process.py` | `prompt, completion` |
| `iris_training-data.csv` | `discord_bot.py` (`load_training_data`, `/claim`, `/ask`) | `prompt, completion, speaker` |
| `daily_summaries.csv` | `hindsight.py` `create_daily_summaries` | `Date, Summary, Binding, Context` |
| `weekly_summaries.csv` | `hindsight.py` `create_weekly_summaries` | `Week_Start_Date, Summary, Binding, Context` |
| `monthly_summaries.csv` | `hindsight.py` `create_monthly_summaries` | `Month_Year, Summary, Binding, Context` |
| `temporal_iris.csv` | `hindsight.py` `construct_daily_training_data` | `Prompt, Completion` |
| `weekly_iris.csv` | `hindsight.py` `construct_weekly_training_data` | `Prompt, Completion` |
| `monthly_iris.csv` | `hindsight.py` `construct_monthly_training_data` | `Prompt, Completion` |

## Provenance note

Raw and derived archives are operator-owned private inputs: do not commit them.
A privacy label or a prompt asking a model to avoid private material is not a filtering
or authorization boundary. Remote processing, retention, caching and logging require
the data steward's approval.

Summary caches carry `iris-summary/v1` bindings to their actual inputs, prompts,
output and recorded prompt time. Cache reuse is recorded-output reuse, not a claim
of deterministic fresh inference. Training-pair outputs carry
`iris-training-pairs/v1` provenance and use a local augmentation seed.
Empty Twitter exports retain the complete schema; ordinary converter output omits
record text, but the resulting CSV still contains the selected private data.

Current Discord attribution/persistence and sketch-bundle changes remain separately
component-qualified; source changes do not rewrite historical attribution strings or
grant consent for live feedback collection.
