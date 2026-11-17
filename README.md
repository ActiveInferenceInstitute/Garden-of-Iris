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
> `davinci` models that no longer exist. Model calls now use the current
> OpenAI SDK surface (`openai >= 3.45.0`) through the in-repo `iris_llm.py`
> client, which routes every request through **OpenRouter**
> (`https://openrouter.ai/api/v1`); the retired fine-tuned model slots map to
> catalog-verified OpenRouter chat models.
> Per-component notes, including what is runnable today, are in
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Contents

- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Requirements](#requirements)
- [Documentation](#documentation)
- [Related projects](#related-projects)
- [License](#license)

## Repository layout

| Path | What it is |
| --- | --- |
| `discord_bot.py` | Discord bot "Iris": pool summarizers, DM relay and `/`-prefixed commands; live/component acceptance remains separate |
| `hindsight.py` | Summarization pipeline: daily → weekly → monthly summaries, plus training-data construction |
| `parse_fourthought.py` | CLI: parse URL/PDF text into printed FourThought types via OpenRouter; not a FourThought-export producer |
| `iris_apparently.py` | Experimental TensorFlow/Keras "DemocraticLLM" transformer sketch (source + temporal embeddings) |
| `iris_llm.py` | Canonical OpenRouter model client (current `openai` SDK surface): `chat()` and `complete()` |
| `twitter_archive.py` | Convert a Twitter archive (`data/tweets.js`) to `twitter_archive.csv` |
| `text_process.py` | Build prompt→completion sentence-pair CSV from a text file (NLTK) |
| `data/semantic-iris.csv` | Training data: `prompt,completion` pairs |
| `data/chat-iris.csv` | Training data: `prompt,completion,Source` triples |
| `tests/` | Core helpers, optional Discord/sketch components, gate contracts and real GNN source/installed admission |
| `scripts/gate.py` | The gate: one entry point whose arms (`syntax`, `docs`, `fast`, `tests`, `models`, `gnn`) CI also runs, plus `admission` for the reviewed-input GNN controls |
| `scripts/check_markdown_links.py` | Gate helper: validates relative links and heading anchors in all markdown |
| `scripts/check_openrouter_models.py` | Gate helper: verifies the scripts' model IDs against the live OpenRouter catalog |
| `scripts/check_gnn_conformance.py` | Gate helper: reviewed bootstrap/manifest admission and guarded pinned parser/checker; explicit no-install source or genuine installed mode |
| `.github/workflows/ci.yml` | CI: the `checks` job (`syntax`, `docs`, `tests`, `models`) and the `gnn conformance (pinned)` job (`gnn`) |
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

`iris_apparently.py` is an unqualified neural sketch, not the bot's trained backend.
Its current component changes need real TensorFlow/sklearn qualification; full training
also requires an authorized `text,source_id,timestamp` dataset and private `--output-dir`.
Historical smoke does not qualify the current source. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#iris_apparentlypy-democraticllm-sketch-repaired-unverified).

## Requirements

Python 3 with the packages used by the individual scripts. The full component
set is listed in [requirements.txt](requirements.txt):

```bash
pip install -r requirements.txt
```

Core development dependencies are listed in [requirements-dev.txt](requirements-dev.txt):

```bash
pip install -r requirements-dev.txt
python scripts/gate.py          # default arm: the offline unit suite
python scripts/gate.py all      # every check, once each (see docs/RUN_GUIDE.md)
```

The complete suite additionally needs the optional component runtimes and the reviewed
GNN inputs described in [tests/README.md](tests/README.md). Missing components/skips do
not qualify those components. `all` includes network/provisioning paths and is not an
offline no-install command. Source/installed subset evidence is not hosted acceptance.

Model calls go through `iris_llm.py`, which builds the current `openai` SDK
client against OpenRouter (https://openrouter.ai/api/v1) and sets the
OpenRouter attribution headers. Scripts read their credentials from
environment variables (see [.env.example](.env.example) for a template):

`chat` and `complete` return stripped, validated first-choice text; an invalid first
choice is refused, not replaced by a later answer. `chat_completion` returns the raw
response, and `response_texts` validates all requested choices. Empty/refused output
raises `ModelOutputError`. Archive processing and live credentials require steward
authorization; a privacy prompt is not a data-exclusion boundary.

| Variable | Used by |
| --- | --- |
| `OPENROUTER_API_KEY` | `discord_bot.py`, `hindsight.py`, `parse_fourthought.py` (primary; falls back to `OPENAI_API_KEY`) |
| `DISCORD_BOT_KEY` | `discord_bot.py` |
| `AIRTABLE_API_KEY` | `discord_bot.py` (tarot deck lookup) |

## Documentation

- [docs/](docs/) — documentation hub
- [docs/documentation-index.md](docs/documentation-index.md) — flat index of long-lived docs
- [docs/RUN_GUIDE.md](docs/RUN_GUIDE.md) — the gate entry point, its arms, and the CI jobs
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — component and pipeline overview
- [docs/DATA.md](docs/DATA.md) — data files, schemas, and generated outputs
- [docs/_generated/GATES.md](docs/_generated/GATES.md) — generated arm table, test inventory, and measured runtimes
- [TO-DO.md](TO-DO.md) — review findings and improvement backlog
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [SECURITY.md](SECURITY.md) — security notes
- [AGENTS.md](AGENTS.md) — working notes for coding agents (gates, layout, boundaries)

## Related projects

This repository sits in the Active Inference Institute's public fleet:

- [Generalized_Notation_Notation](https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation) —
  the fleet's specification core for Active Inference generative models. See
  its
  [integration guide](https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation/blob/main/docs/gnn/integration/framework_integration_guide.md)
  and
  [implementation guide](https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation/blob/main/docs/gnn/integration/gnn_implementation.md).
  GNN maintains a
  [downstream adoption guide](https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation/blob/main/docs/gnn/integration/downstream_adoption.md)
  for repositories that consume the notation.
- [active_inference_language_model](https://github.com/ActiveInferenceInstitute/active_inference_language_model) —
  a discrete language stack whose levels are specified in GNN; the closest
  fleet counterpart to Iris's typed-thought pipeline.
- [courses](https://github.com/ActiveInferenceInstitute/courses) — curriculum
  material, including the Generalized Notation Notation stream episodes.

Garden-of-Iris itself specifies no Active Inference generative model today:
the FourThought typing is prompt-driven classification, and the Iris LM is a
neural architecture sketch. If a typed-thought generative model (for example a
claim-verification model over the FourThought categories) is added later, it
should be specified in GNN and validated against a pinned parser revision, as
the fleet repos above do.

## License

[CC BY 4.0](LICENSE) — Creative Commons Attribution 4.0 International, the
Active Inference Institute's standard open license. See
[CITATION.cff](CITATION.cff) for citation information.
