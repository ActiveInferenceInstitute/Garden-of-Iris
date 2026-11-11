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

## Run

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

CI (`.github/workflows/ci.yml`) runs `python -m compileall -q .`, the markdown
link checker, this suite, and the live OpenRouter model-ID check. The
documentation for the components these tests exercise is in
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
