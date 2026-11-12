# Garden-of-Iris — agent notes

Experimental toolkit for **Iris** (a collective-intelligence language model)
and the FourThought dialectic data pipeline. Stewarded by the Active Inference
Institute; published under CC BY 4.0. See [README.md](README.md) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the human-facing overview.

## Layout and contracts

- Root scripts are the application: `discord_bot.py`, `hindsight.py`,
  `parse_fourthought.py`, `iris_apparently.py`, `twitter_archive.py`,
  `text_process.py`.
- `iris_llm.py` is the single home for model calls: the OpenRouter client on
  the current `openai` SDK surface, API-key resolution
  (`OPENROUTER_API_KEY`, falling back to `OPENAI_API_KEY`), and the OpenRouter
  attribution headers. Do not add a second client, a legacy shim, or direct
  `openai` calls in scripts.
- `data/semantic-iris.csv` and `data/chat-iris.csv` are the only tracked data
  files. Personal archives (`data/tweets.js`,
  `prophet_thought_dump_ALL_THOUGHTS_2023.csv`, `tarot_text.csv`) and
  generated CSVs are untracked — never commit them.
- FourThought semantics (thought types, truth/good voting) are described in
  `docs/ARCHITECTURE.md` and `docs/DATA.md`; keep those descriptions in sync
  with the code.

## Gates (run before publishing)

One entry point, `scripts/gate.py`; `.github/workflows/ci.yml` runs these same
arms, so a local run is the gate. Arms: `syntax`, `docs`, `fast`, `tests`,
`models`, `gnn`.

```bash
pip install -r requirements-dev.txt
python scripts/gate.py          # default arm: fast (offline unit suite)
python scripts/gate.py all      # syntax, docs, tests, models (network), gnn
python scripts/gate.py list     # the arm table with exact commands
```

There is no `types` arm: the repository has no static type checker. The `gnn`
arm installs the parser revision pinned in `.github/gnn-pin.json` and needs
Python 3.12 (the CI pin); that package declares `requires-python
>=3.11,<3.15`. Measured arm runtimes and the test inventory live in
[docs/_generated/GATES.md](docs/_generated/GATES.md), which
`python scripts/gate.py report` regenerates — never hand-edit those numbers.
See [docs/RUN_GUIDE.md](docs/RUN_GUIDE.md).

The test suite stubs the model client; it needs no API key. A real end-to-end
run of `discord_bot.py`, `hindsight.py`, or `parse_fourthought.py` requires
credentials and the personal-archive inputs, which are not in the repository —
do not claim live model results from a stubbed run.

## Boundaries

- No secrets in the tree. Credentials come from environment variables
  (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `DISCORD_BOT_KEY`,
  `AIRTABLE_API_KEY`).
- `iris_apparently.py` is a sketch: a training run needs a
  `text, source_id, timestamp` CSV that is not committed. Do not claim
  training results.
- Discord channel IDs are hardcoded for the original server layout; do not
  generalize behavioral claims beyond that layout.

## Generalized Notation Notation (GNN)

This repository defines no Active Inference generative model — the FourThought
typing is prompt-driven classification and the Iris LM is a neural
architecture sketch — so it carries no `.gnn.md` model file. If a generative
model is added, for example a claim-verification model over the FourThought
categories, specify it in GNN and validate it against a pinned parser
revision:

- GNN repository: https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation
- Integration guide: https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation/blob/main/docs/gnn/integration/framework_integration_guide.md
- Implementation guide: https://github.com/ActiveInferenceInstitute/Generalized_Notation_Notation/blob/main/docs/gnn/integration/gnn_implementation.md
- Related fleet repositories: [active_inference_language_model](https://github.com/ActiveInferenceInstitute/active_inference_language_model)
  (GNN-specified language stack), [courses](https://github.com/ActiveInferenceInstitute/courses)
  (GNN stream episodes), [Active_Inference_Ontology](https://github.com/ActiveInferenceInstitute/Active_Inference_Ontology).
