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

There is no `types` arm. The `gnn` arm requires independently reviewed bootstrap
and manifest inputs before candidate import; use explicit no-install source or
genuine installed-origin qualification as described in `.github/GNN.md`.
The pinned package requires Python `>=3.11,<3.15`; CI selects Python 3.12.
Source proof is not installed, native, scientific or hosted proof.
Historical arm wall times, test inventory and before/after comparison live in
[docs/_generated/GATES.md](docs/_generated/GATES.md);
`python scripts/gate.py measure --label before|after` writes the timing
receipts and `python scripts/gate.py report` renders them — never hand-edit
those numbers.
See [docs/RUN_GUIDE.md](docs/RUN_GUIDE.md).

Core unit tests substitute the model transport and need no API key; GNN tests use
real parser/checker processes. Optional Discord/TensorFlow/PDF/browser components
need genuine prepared runtimes and, for live operations, owner-approved inputs and
credentials. A skipped component or historical smoke does not qualify current source.
Never infer privacy authorization from a prompt label or claim live results from
transport substitutions.

## Boundaries

- No secrets in the tree. Credentials come from environment variables
  (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `DISCORD_BOT_KEY`,
  `AIRTABLE_API_KEY`).
- `iris_apparently.py` retains a same-sequence reconstruction objective, not a
  qualified causal next-token model. Its current component changes remain unqualified
  without real TensorFlow/sklearn proof; full training needs a steward-authorized
  `text,source_id,timestamp` dataset and private `--output-dir`.
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
