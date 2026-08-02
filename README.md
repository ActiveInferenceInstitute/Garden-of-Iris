# Garden-of-Iris

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

> **Status: experimental.** These scripts were developed in 2022–2023 against
> the legacy OpenAI API (`openai.Completion` / `openai.ChatCompletion`, package
> version `<1.0`) and fine-tuned `davinci` models that no longer exist. They are
> shared for study and reuse, not maintained as production software. Not every
> script runs as-is today; see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for
> per-component notes.

## Repository layout

| Path | What it is |
| --- | --- |
| `discord_bot.py` | Discord bot "Iris": pool summarizers, DM relay, slash commands |
| `hindsight.py` | Summarization pipeline: daily → weekly → monthly summaries, plus training-data construction |
| `parse_fourthought.py` | CLI: parse a URL or PDF into FourThought thought types via OpenAI |
| `iris_apparently.py` | Unfinished TensorFlow/Keras "DemocraticLLM" transformer sketch (source + temporal embeddings) |
| `twitter_archive.py` | Convert a Twitter archive (`data/tweets.js`) to `twitter_archive.csv` |
| `text_process.py` | Build prompt→completion sentence-pair CSV from a text file (NLTK) |
| `data/semantic-iris.csv` | Training data: `prompt,completion` pairs |
| `data/chat-iris.csv` | Training data: `prompt,completion,Source` triples |
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

# Run the hindsight summarization pipeline
# (expects prophet_thought_dump_ALL_THOUGHTS_2023.csv and twitter_archive.csv)
python hindsight.py

# Run the Discord bot (requires the environment variables below)
python discord_bot.py
```

`iris_apparently.py` is a non-runnable sketch; see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#iris_apparentlypy-democraticllm-sketch-not-runnable) for the known
blockers.

## Requirements

Python 3 with the packages used by the individual scripts. A full install for
every component looks like:

```bash
pip install openai<1.0 discord.py pandas tensorflow nltk PyPDF2 selenium beautifulsoup4 tqdm pyairtable python-dateutil
```

Scripts read their credentials from environment variables (see
[.env.example](.env.example) for a template):

| Variable | Used by |
| --- | --- |
| `OPENAI_API_KEY` | `discord_bot.py`, `hindsight.py`, `parse_fourthought.py` |
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
