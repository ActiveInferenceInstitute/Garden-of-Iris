# GNN conformance

The conformance check is the `gnn` arm of `scripts/gate.py`, implemented once
in `scripts/check_gnn_conformance.py`. CI runs it as job key `gnn-conformance`,
display name `gnn conformance (pinned)`, in
[`workflows/ci.yml`](workflows/ci.yml).

It reads [`gnn-pin.json`](gnn-pin.json) (schema `gnn-importer-pin/v1`), which
pins `ActiveInferenceInstitute/Generalized_Notation_Notation` at `v5.0.3`
(`8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`, recorded 2026-11-12), installs
that exact revision with `--no-deps`, and checks the installed parser reports
version `5.0.3`.

What it parses: every `*.gnn.md` sketch under the repository root, excluding
`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, and
`.mypy_cache` — each sketch is parsed, syntax-checked, and type-checked by the
pinned `GNNTypeChecker`. When the repository has no sketch yet, the baseline is
the pinned upstream `input/gnn_files/basics/static_perception.md` exemplar,
parsed and type-checked the same way; the check prints a JSON summary naming
`"source": "pinned-exemplar"`. The type check accepts only the pinned
`GNNTypeChecker`'s literal `True`: `2` (completed with warnings — invalid
files, or no files found) and `False` (a hard failure) both stop the arm, and
the refusal names the value the checker returned. This is a pipeline and pin
conformance baseline, not a claim that the repository already contains a model.

The pinned package declares `requires-python >=3.11,<3.15`, so run the arm on
Python 3.12 (the CI pin). Details and measured runtimes:
[`../docs/RUN_GUIDE.md`](../docs/RUN_GUIDE.md).
