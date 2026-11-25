# GNN conformance

The conformance check is the `gnn` arm of `scripts/gate.py`, implemented once
in `scripts/check_gnn_conformance.py`. CI runs it as job key `gnn-conformance`,
display name `gnn conformance (pinned)`, in
[`workflows/ci.yml`](workflows/ci.yml).

It reads [`gnn-pin.json`](gnn-pin.json) (schema `gnn-importer-pin/v1`), which
pins `ActiveInferenceInstitute/Generalized_Notation_Notation` at `v5.1.0`
(`75c834bd8519dc7b5adc4d24f16bf393cfd1ecdf`, recorded 2026-11-24). Before importing
GNN it verifies standalone bootstrap bytes and an independently frozen complete
manifest, selected by `GNN_BOOTSTRAP` and `GNN_SOURCE_MANIFEST`.
Installed mode requires genuine exact Git distribution provenance, import ownership
and full package-content agreement; matching version text is not sufficient.
Explicit `GNN_ORIGIN_MODE=source` instead requires `GNN_PACKAGE_ROOT` and reports
`explicit-source`, not installed provenance. A refused origin never falls back.

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

`GNN_EXEMPLAR` can select an admitted real local exemplar instead of remote
acquisition. `GNN_NO_INSTALL=1` prohibits installation. All actual parser/checker
calls share the qualified-source lifetime and its exit revalidation before the
receipt is published. Preserve any type-check warning sentinel; no source or
installed verdict proves native execution or scientific semantics.
Hosted delivery of reviewed resources remains separately required.

The pinned package declares `requires-python >=3.11,<3.15`, so run the arm on
Python 3.12 (the CI pin). Details and measured runtimes:
[`../docs/RUN_GUIDE.md`](../docs/RUN_GUIDE.md).
