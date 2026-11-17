# `tests/`

Pytest suite for Garden-of-Iris. Core model-transport substitutions need no API key,
but they do not prove a live service. GNN controls use actual parser/checker processes;
Discord and neural-sketch tests require genuine prepared component dependencies.
Missing components or skipped cases are unqualified prerequisites, not successes.

## Files

| File | Covers |
| --- | --- |
| [`conftest.py`](conftest.py) | Shared fixture: puts the repository root on `sys.path` so the root modules import. |
| [`test_iris_llm.py`](test_iris_llm.py) | The `iris_llm` client: client construction, request shapes, and helpers (a stub `openai` module replaces the SDK). |
| [`test_parse_fourthought.py`](test_parse_fourthought.py) | `parse_fourthought`: text cleaning, chunking, the thought-type classifier, and the chunk-by-chunk model loop with a stubbed call. |
| [`test_hindsight.py`](test_hindsight.py) | `hindsight`: chunk balancing, the stubbed summary call, and CLI usage. |
| [`test_data_tools.py`](test_data_tools.py) | `text_process` and `twitter_archive` data-tool helpers. |
| [`test_no_legacy_api.py`](test_no_legacy_api.py) | Guard that no legacy pre-1.0 API surface or `openai_legacy` shim returns. |
| [`test_discord_bot.py`](test_discord_bot.py) | Real Discord types with offline transport boundaries; requires the prepared Discord/Airtable component runtime |
| [`test_iris_apparently.py`](test_iris_apparently.py) | Real TensorFlow/sklearn engineering and private-bundle controls, not scientific training acceptance |
| [`test_gate_cli.py`](test_gate_cli.py) | Administrative/arm argument and authored-syntax contracts |
| [`test_gnn_conformance.py`](test_gnn_conformance.py) | Real pinned parser/checker, literal-`True` acceptance and actual invalid-dimension refusals, source inventory, checked bootstrap and verdict-lifetime controls |

## Run

```bash
pip install -r requirements-dev.txt
python scripts/gate.py fast    # this suite, offline: `-m "not network"`
python scripts/gate.py tests   # the whole suite
```

`fast` excludes the `network` marker; CI runs `tests`, not both overlapping arms.
Do not maintain a handwritten test count; inspect the actual executed roster and
distinguish missing optional components from passing cases.

The GNN module carries the `gnn_resources` marker and runs only under
`--gnn-admission` (`python scripts/gate.py admission`); `fast` and `tests`
deselect it. Under that option it requires explicit `GNN_BOOTSTRAP`,
`GNN_SOURCE_MANIFEST`, `GNN_PACKAGE_ROOT` and `GNN_EXEMPLAR` inputs, and a missing
input is a failed prerequisite, not a skip. It copies real reviewed resources into
private fixtures outside the consumer's model-discovery root and installs nothing.
Source-mode proof does not replace separate genuine installed-origin qualification,
and neither establishes native execution or scientific validity.

See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) and
[`../docs/RUN_GUIDE.md`](../docs/RUN_GUIDE.md). Generated historical timing/inventory
receipts are not current proof when their source or command population has changed.
