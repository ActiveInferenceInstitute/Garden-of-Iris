# `.github/`

- [`workflows/ci.yml`](workflows/ci.yml) — CI. Every step runs one arm of
  `scripts/gate.py`; the workflows hold no command of their own.
  - job key `checks` (display name `checks`): installs
    `requirements-dev.txt` once on Python 3.12 and runs the `syntax`, `docs`,
    `tests`, and `models` arms.
  - job key `gnn-conformance` (display name `gnn conformance (pinned)`): runs
    the `gnn` arm, which installs the pinned parser revision and verifies it
    through [`../scripts/check_gnn_conformance.py`](../scripts/check_gnn_conformance.py).
  - Both jobs pin `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`
    (v7.0.1) and `actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0`
    (v7.1.0); the workflow does not use a composite setup action.
- [`dependabot.yml`](dependabot.yml) — dependency update configuration.
- [`gnn-pin.json`](gnn-pin.json) — the canonical GNN pin, schema
  `gnn-importer-pin/v1`: `ActiveInferenceInstitute/Generalized_Notation_Notation`
  at tag `v5.0.3`, revision `8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`,
  recorded 2026-11-12. It is the only source of the pin; the conformance code
  reads it and fails on a schema, repository, or revision mismatch.
- [`GNN.md`](GNN.md) — what the pinned GNN conformance arm checks.

Repository gates and boundaries are in [`../AGENTS.md`](../AGENTS.md); the gate
entry point and measured arm runtimes are in
[`../docs/RUN_GUIDE.md`](../docs/RUN_GUIDE.md) and
[`../docs/_generated/GATES.md`](../docs/_generated/GATES.md); the test suite is
described in [`../tests/README.md`](../tests/README.md).
