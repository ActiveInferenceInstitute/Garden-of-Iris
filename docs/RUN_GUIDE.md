# Run guide — the gate and CI

This repository has **one gate entry point**: `scripts/gate.py`. Each arm is a
single command, defined once in that script; `.github/workflows/ci.yml` invokes
the arms and holds no command of its own, so a local run and a CI run execute
the same argv.

## Quick start

```bash
pip install -r requirements-dev.txt
python scripts/gate.py          # default arm: fast
python scripts/gate.py all      # every distinct check, once each
python scripts/gate.py list     # the arm table with the exact commands
```

The exact command of every arm, the current test inventory, and the measured
before/after wall times are in the generated
[`_generated/GATES.md`](_generated/GATES.md). It is rendered from committed
receipts, not from prose: `python scripts/gate.py measure --label before`
records the pre-gate commands and `--label after` records the gate arms, one
pass per arm, each into `docs/_generated/gate-<label>.json`;
`python scripts/gate.py report` renders the facts and the comparison. The
`docs` arm runs `report --check`, which fails when the committed arms, test
counts, or receipt commands no longer match the code.

Refresh order after changing an arm: `report` (writes the facts the freshness
check compares against), then `measure --label after`, then `report`. Re-run
`measure --label before` only if the recorded baseline changes.

## Arms

| Arm | What it checks | Needs |
| --- | --- | --- |
| `syntax` | Compiles every module. This is the repository's only lint gate: there is no static linter, formatter, or type checker, so there is no `types` arm. | Python only |
| `docs` | Relative markdown links and heading anchors, then the generated-number freshness check. | `requirements-dev.txt` |
| `fast` | The offline unit suite (`-m "not network"`). This is the default arm. | `requirements-dev.txt` |
| `tests` | The whole unit suite. | `requirements-dev.txt` |
| `models` | The scripts' model IDs exist in the live OpenRouter catalog. | Network |
| `gnn` | Pinned GNN conformance: install `.github/gnn-pin.json`'s parser revision, parse and type-check the repository's GNN sketches. | Network, Python 3.12 |

`fast` is the offline subset of `tests`; `pytest.ini` declares the `network`
marker, and no test carries it today, so both arms collect the same suite. `all`
runs `syntax`, `docs`, `tests`, `models`, and `gnn` — it does not run `fast`
again, because `tests` covers it.

## Interpreter

CI pins Python 3.12. The `gnn` arm requires it: the pinned
`generalized-notation-notation` package declares `requires-python
>=3.11,<3.15`, so the arm refuses to install on 3.15 and later. Other arms run
on any supported Python 3.

## CI

`.github/workflows/ci.yml` has two jobs:

| Job key | Display name | Arms |
| --- | --- | --- |
| `checks` | `checks` | `syntax`, `docs`, `tests`, `models` on Python 3.12, after one `requirements-dev.txt` install |
| `gnn-conformance` | `gnn conformance (pinned)` | `gnn` |

CI installs the test dependencies once per job and never runs both `fast` and
`tests`. GitHub Actions billing for this repository's organisation is
unavailable, so local gate runs are the only executable gate; a green local
`all` is evidence about this host, not about a hosted run.

## GNN pin

- Pin file: [`.github/gnn-pin.json`](../.github/gnn-pin.json), schema
  `gnn-importer-pin/v1`.
- Pinned revision: `ActiveInferenceInstitute/Generalized_Notation_Notation` at
  tag `v5.0.3`, revision `8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`, recorded
  2026-11-12.
- Pointer: [`.github/GNN.md`](../.github/GNN.md) records what the conformance
  job parses and which sketch set counts.
- Implementation: `scripts/check_gnn_conformance.py`; the arm fails on a schema,
  repository, revision, or installed-version mismatch.

## Documentation check

The `docs` arm runs `scripts/check_markdown_links.py`, which validates relative
links and heading anchors across every markdown file in the repository, then
`python scripts/gate.py report --check`. The repository has no mkdocs site and
no markdown-link-check configuration; the script is its own check.
