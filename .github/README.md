# `.github/`

- [`workflows/ci.yml`](workflows/ci.yml) — CI: Python syntax check, the
  markdown link/anchor checker, the pytest suite, and the live OpenRouter
  model-ID catalog check, plus the pinned GNN conformance job.
- [`dependabot.yml`](dependabot.yml) — dependency update configuration.
- [`gnn-pin.json`](gnn-pin.json) — the pinned Generalized Notation Notation
  revision (v5.0.3, commit `8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`) used by
  the conformance job.
- [`GNN.md`](GNN.md) — what the pinned GNN conformance job checks.

Repository gates and boundaries are in [`../AGENTS.md`](../AGENTS.md); the test
suite is described in [`../tests/README.md`](../tests/README.md).
