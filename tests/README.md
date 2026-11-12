# `tests/`

Pytest suite for the Garden-of-Iris scripts. The tests stub the model client,
so they need no API key and no network access; only the OpenRouter catalog
check under `scripts/` touches the network, and it is not part of this suite.

## Files

| File | Covers |
| --- | --- |
| [`conftest.py`](conftest.py) | Shared fixture: puts the repository root on `sys.path` so the root modules import. |
| [`test_iris_llm.py`](test_iris_llm.py) | The `iris_llm` client: client construction, request shapes, and helpers (a stub `openai` module replaces the SDK). |
| [`test_parse_fourthought.py`](test_parse_fourthought.py) | `parse_fourthought`: text cleaning, chunking, the thought-type classifier, and the chunk-by-chunk model loop with a stubbed call. |
| [`test_hindsight.py`](test_hindsight.py) | `hindsight`: chunk balancing, the stubbed summary call, and CLI usage. |
| [`test_data_tools.py`](test_data_tools.py) | `text_process` and `twitter_archive` data-tool helpers. |
| [`test_no_legacy_api.py`](test_no_legacy_api.py) | Guard that no legacy pre-1.0 API surface or `openai_legacy` shim returns. |
| [`test_gnn_conformance_gate.py`](test_gnn_conformance_gate.py) | `scripts/check_gnn_conformance.py` accepts only the pinned checker's literal `True`; `2`, `False`, `None`, and `0` are refusals that name the returned value. |

## Run

```bash
pip install -r requirements-dev.txt
python scripts/gate.py fast    # this suite, offline: `-m "not network"`
python scripts/gate.py tests   # the whole suite
```

`pytest.ini` declares the `network` marker; no test carries it today, so `fast`
and `tests` collect the same 47 tests. CI (`.github/workflows/ci.yml`) runs the
`tests` arm of `scripts/gate.py` — not both — alongside the `syntax`, `docs`,
and `models` arms, and the `gnn-conformance` job runs the `gnn` arm. The
documentation for the components these tests exercise is in
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md), and the arm table plus
measured numbers are in [`../docs/_generated/GATES.md`](../docs/_generated/GATES.md).
