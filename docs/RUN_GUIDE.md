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

After an arm changes, generated inventory and measured receipt commands may be stale.
`report` renders facts but does not remeasure an arm or qualify unchanged receipt text.
New `measure --label after` work requires authorization for every included arm
(including network/model/GNN provisioning); preserve the historical `before` receipt.
Do not hand-edit measured numbers or mark `docs` green while `report --check` fails.

## Arms

| Arm | What it checks | Needs |
| --- | --- | --- |
| `syntax` | Compiles authored Python into disposable output, excluding environments/caches. No static linter, formatter or type checker is claimed. | Python only |
| `docs` | Publishing artifact digests and drift selftest, canonical relative links/anchors and docs-index coverage, then generated-number freshness. | `requirements-dev.txt` |
| `fast` | Offline-marked unit selection (`-m "not network"`); default arm; deselects `gnn_resources` | Core dependencies; optional component prerequisites remain explicit |
| `tests` | Whole unit suite except `gnn_resources` (deselected) | All actual component runtimes |
| `models` | The scripts' model IDs exist in the live OpenRouter catalog. | Network |
| `gnn` | Guarded pinned parser/checker with reviewed bootstrap/manifest; source and installed modes are distinct | Prepared compatible Python and reviewed inputs; default acquisition/provisioning may need network |
| `admission` | `tests/test_gnn_conformance.py` under `--gnn-admission`: reviewed-input admission controls | `GNN_BOOTSTRAP`, `GNN_SOURCE_MANIFEST`, `GNN_PACKAGE_ROOT`, `GNN_EXEMPLAR`; a missing input fails |

`fast` is the offline subset of `tests`; `pytest.ini` declares the `network`
marker, and no test carries it today, so both arms collect the same suite. `all`
runs `syntax`, `docs`, `tests`, `models`, and `gnn` — it does not run `fast`
again, because `tests` covers it. `admission` is outside `all`, `measure` and CI
until hosted delivery of the reviewed GNN inputs exists; run it wherever those
inputs are bound.

Administrative modes `list`, `report` and `measure` must stand alone; mixed commands
or unknown trailing arguments fail before executing an arm or writing a report.

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
- Implementation: `scripts/check_gnn_conformance.py`; pin reading uses independently
  checked standalone bootstrap bytes. The independently frozen complete manifest,
  import ownership, source/origin and lifetime exit checks must all agree before a
  verdict is emitted. Version equality alone is insufficient.

For no-install use, supply `GNN_BOOTSTRAP`, `GNN_SOURCE_MANIFEST` and an actual
`GNN_EXEMPLAR` local model when no repository sketches exist. Explicit source mode
also requires `GNN_ORIGIN_MODE=source` and `GNN_PACKAGE_ROOT`; it never qualifies an
installed distribution. `GNN_NO_INSTALL=1 python scripts/gate.py gnn` preserves the
selected real interpreter. Installed mode requires genuine exact Git PEP610 ownership
and complete package-content agreement. Neither mode proves native execution or
scientific semantics; `execution_verified` remains false.
The regression module uses these reviewed inputs and actual parser/checker processes.
Hosted resource delivery is a separate prerequisite, not implied by local proof.

## Documentation check

The `docs` arm runs `scripts/check_markdown_links.py`, a member adapter for the
digest-pinned [Publishing checks](workflows/publishing.md). It verifies the
canonical schema and every copied module/pin, exercises the canonical drift
selftest, and delegates links, anchors and index coverage to the canonical docs
module. Markdown scope still includes new files and excludes dependency/cache
directories. The arm then runs `python scripts/gate.py report --check`.

The existing generated timing receipts predate the Publishing migration; their
unchanged command lines do not measure the added digest and index checks.
The repository has no mkdocs site or markdown-link-check configuration.
