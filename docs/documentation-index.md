# Documentation index

A flat index of the long-lived documents in this repository. The
[hub](README.md) explains how they fit together; this page is the lookup list.

## Repository documents

| Document | Purpose |
| --- | --- |
| [README.md](../README.md) | Overview, repository layout, quick start, requirements, environment variables, license |
| [AGENTS.md](../AGENTS.md) | Working notes for coding agents: layout, gates, boundaries, GNN signposting |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution rules and the verify steps |
| [SECURITY.md](../SECURITY.md) | Security notes and secret handling |
| [CITATION.cff](../CITATION.cff) | Citation metadata |
| [TO-DO.md](../TO-DO.md) | Review findings and improvement backlog |
| [REVIEW_LOG_2026-08-02.md](../REVIEW_LOG_2026-08-02.md) | Point-in-time review record |
| [LICENSE](../LICENSE) | CC BY 4.0 license text |

## `docs/`

| Document | Purpose |
| --- | --- |
| [README.md](README.md) | Documentation hub |
| [documentation-index.md](documentation-index.md) | This flat index |
| [RUN_GUIDE.md](RUN_GUIDE.md) | The gate entry point (`scripts/gate.py`), its arms, the CI jobs, and the GNN pin |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component-by-component overview, data flow, FourThought dialectic, tests and CI |
| [DATA.md](DATA.md) | Tracked training data, expected inputs, generated outputs, column schemas |
| [_generated/GATES.md](_generated/GATES.md) | Generated: arm table, test inventory, measured runtimes (producer `scripts/gate.py report`) |

## Generated documents

Numbers that a script can produce live in a generated document, never in prose:

| Document | Producer | Check |
| --- | --- | --- |
| [_generated/GATES.md](_generated/GATES.md) | `python scripts/gate.py measure --label before` and `--label after` (receipts), then `python scripts/gate.py report` | `python scripts/gate.py report --check` (the `docs` arm) |
| [_generated/gate-before.json](_generated/gate-before.json), [_generated/gate-after.json](_generated/gate-after.json) | `python scripts/gate.py measure` (one pass per arm) | `python scripts/gate.py report --check` (commands must match the code) |

## Folder-level guides

| Path | Guide |
| --- | --- |
| `.github/` | [`.github/README.md`](../.github/README.md), [`.github/GNN.md`](../.github/GNN.md) |
| `tests/` | [`tests/README.md`](../tests/README.md) |
| `.aii/` | [`.aii/README.md`](../.aii/README.md), [`.aii/AGENTS.md`](../.aii/AGENTS.md), [`.aii/docs/INTEGRATION.md`](../.aii/docs/INTEGRATION.md) |
