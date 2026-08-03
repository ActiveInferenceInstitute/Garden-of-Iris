# Garden-of-Iris

[![CI](https://github.com/ActiveInferenceInstitute/Garden-of-Iris/actions/workflows/ci.yml/badge.svg)](https://github.com/ActiveInferenceInstitute/Garden-of-Iris/actions/workflows/ci.yml)

Experimental toolkit for **Iris** — a collective-intelligence language model —
and the data pipeline that feeds it. This repository is stewarded by the
[Active Inference Institute](https://www.activeinference.org).

Iris is an experiment in *democratic* language modeling: a model trained on
community contributions and oriented around the **FourThought dialectic**, in
which every thought is tagged by its temporal focus and certainty:

| Thought type | Temporal focus | Description |
| --- | --- | --- |
| `PREDICTION` | Future | Claims about the future; verifiable only as time passes |
| `REFLECTION` | Past | Claims about the past; verifiable against records |
| `STATEMENT` | Present | Claims about the present; verifiable by the community |
| `QUESTION` | Any | Queries born of uncertainty, not declarations of truth |

The repo contains a Discord bot that acts as an "oracle / time compass" for a
community, a hindsight summarization pipeline that turns years of tagged
thoughts into daily/weekly/monthly summaries and fine-tuning data, a CLI that
parses scraped web text into the four thought types, and an unfinished
TensorFlow sketch of an Iris model architecture.

> **Status: experimental.** These scripts were developed in 2022–2023 and are
> shared for study and reuse rather than maintained as production software.
> They originally targeted the legacy pre-1.0 OpenAI package and fine-tuned
> `davinci` models that no longer exist. The in-repo `openai_legacy.py` shim
> patches the legacy call style onto `openai >= 1.0` and routes every request
> through **OpenRouter** (`https://openrouter.ai/api/v1`); the retired
> fine-tuned model slots now map to catalog-verified OpenRouter chat models.
> Per-component notes, including what is runnable today, are in
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository layout

| Path | What it is |
| --- | --- |
| `discord_bot.py` | Discord bot "Iris": pool summarizers, DM relay, slash commands |
| `hindsight.py` | Summarization pipeline: daily → weekly → monthly summaries, plus training-data construction |
| `parse_fourthought.py` | CLI: parse a URL or PDF into FourThought thought types via OpenAI |
| `iris_apparently.py` | Experimental TensorFlow/Keras "DemocraticLLM" transformer sketch (source + temporal embeddings) |
| `openai_legacy.py` | Compatibility shim: legacy `openai.Completion` / `ChatCompletion` calls routed through OpenRouter |
| `twitter_archive.py` | Convert a Twitter archive (`data/tweets.js`) to `twitter_archive.csv` |
| `text_process.py` | Build prompt→completion sentence-pair CSV from a text file (NLTK) |
| `data/semantic-iris.csv` | Training data: `prompt,completion` pairs |
| `data/chat-iris.csv` | Training data: `prompt,completion,Source` triples |
| `scripts/check_markdown_links.py` | CI helper: validates relative links and heading anchors in all markdown |
| `scripts/check_openrouter_models.py` | CI helper: verifies the scripts' model IDs against the live OpenRouter catalog |
| `.github/workflows/ci.yml` | CI: Python syntax, markdown links, openai shim smoke test |
| `.aii/config.yaml` | InstituteOS sidecar metadata |
| `LICENSE` | CC BY 4.0 license text |

## Quick start

```bash
# Parse a URL into FourThought thought types
python parse_fourthought.py https://example.com

# Parse a PDF into FourThought thought types
python parse_fourthought.py /path/to/paper.pdf

# Convert a Twitter archive export into a CSV (needs data/tweets.js)
python twitter_archive.py

# Run the hindsight summarization pipeline (stages are flags; see python hindsight.py --help)
python hindsight.py --daily        # needs the FourThought dump + twitter_archive.csv
python hindsight.py --weekly       # needs daily_summaries.csv
python hindsight.py --monthly      # needs weekly_summaries.csv
python hindsight.py --all          # full pipeline in order

# Run the Discord bot (requires the environment variables below)
python discord_bot.py
```

`iris_apparently.py` imports and its training flow is structurally consistent,
but it is an unverified sketch: training requires TensorFlow and a CSV with
`text, source_id, timestamp` columns, none of which is committed. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#iris_apparentlypy-democraticllm-sketch-repaired-unverified).

## Requirements

Python 3 with the packages used by the individual scripts. A full install for
every component looks like:

```bash
pip install "openai>=1.0" discord.py pandas tensorflow nltk PyPDF2 selenium beautifulsoup4 tqdm pyairtable python-dateutil
```

The scripts call the legacy pre-1.0 OpenAI API style; `openai_legacy.py`
(shipped in this repository) patches that surface onto `openai >= 1.0` and
routes all model calls through OpenRouter (https://openrouter.ai/api/v1), so
current package versions work without code changes. Scripts read their
credentials from environment variables (see [.env.example](.env.example) for a
template):

| Variable | Used by |
| --- | --- |
| `OPENROUTER_API_KEY` | `discord_bot.py`, `hindsight.py`, `parse_fourthought.py` (primary; falls back to `OPENAI_API_KEY`) |
| `DISCORD_BOT_KEY` | `discord_bot.py` |
| `AIRTABLE_API_KEY` | `discord_bot.py` (tarot deck lookup) |

## Documentation

- [docs/](docs/) — documentation index
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — component and pipeline overview
- [docs/DATA.md](docs/DATA.md) — data files, schemas, and generated outputs
- [TO-DO.md](TO-DO.md) — review findings and improvement backlog
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [SECURITY.md](SECURITY.md) — security notes

## License

[CC BY 4.0](LICENSE) — Creative Commons Attribution 4.0 International, the
Active Inference Institute's standard open license. See
[CITATION.cff](CITATION.cff) for citation information.
