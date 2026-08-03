# Review log — 2026-08-02

Documentation-deep review pass on Garden-of-Iris. Branch: `master`
(tracking `origin/master`, the default branch per `origin/HEAD`).
Base HEAD before the pass: `a17e62f`.

## Phase 0 — Preflight

- `git fetch origin`; already on `master`, fast-forward clean.
- Inventory at start (9 tracked files): `.aii/config.yaml`, `LICENSE`,
  `data/chat-iris.csv`, `data/semantic-iris.csv`, `discord_bot.py`,
  `hindsight.py`, `iris_apparently.py`, `parse_fourthought.py`,
  `text_process.py`, `twitter_archive.py`.
- **Absent:** README, `docs/`, AGENTS.md/CLAUDE.md, CI (`.github/`), any
  TODO/ROADMAP file, CONTRIBUTING.md, SECURITY.md, CITATION.cff,
  `.gitignore`, `.env.example`.
- The repository is an experimental "Iris" collective-intelligence toolkit:
  a Discord bot, a hindsight summarization pipeline over the FourThought
  dialectic, a web/PDF thought-type parser CLI, an unfinished TensorFlow
  transformer sketch, and data tooling, plus two tracked training CSVs.
- Cheap validations: all six Python files pass `ast.parse` (syntax-valid).
  No test suite exists. Runtime dependencies (legacy `openai < 1.0`,
  `tensorflow`, `discord.py`, Selenium) and personal-archive inputs were
  **not** exercised — the scripts were not executed.

## Phase 1 — Mega-deep docs review

Full scoped findings with file paths live in [TO-DO.md](TO-DO.md);
3 Major, 6 Medium, 3 Minor. Headline results:

- A public repository with **zero entry documentation**: no README, no docs
  index, no contribution or security policy, no citation file.
- **Doc/code drift:** `parse_fourthought.py` usage comments referenced
  `parse_claims.py`, which no longer exists in the tree; the `.aii` sidecar
  description was a generic placeholder and its `meta.updated` date was stale.
- **Undocumented status:** all scripts target the legacy pre-1.0 OpenAI API
  and retired fine-tuned `davinci` models; `discord_bot.py` hardcodes channel
  IDs; `iris_apparently.py` is a non-runnable sketch (verified blockers:
  `layers` never imported, module-level calls before definitions at lines
  56/79, `fit` signature mismatch, unused helpers).
- **Undocumented data:** tracked CSVs had no schema docs; expected inputs
  (personal archives) and generated outputs were unprotected by `.gitignore`.
- No existing docs to lint; markdown quality issues were introduced only by
  this pass and are covered under N3.

## Phase 2 — Scope

Created [TO-DO.md](TO-DO.md) at the repo root with Minor / Medium / Major
sections; every Phase 1 finding is scoped with file paths; completed items
carry commit references; open items are listed at the end.

## Phase 3 — Implementation

Commits (chronological):

| Commit | Change |
| --- | --- |
| `2b3f778` | docs: add root README |
| `43e4fe4` | docs: add documentation index, architecture overview, and data reference |
| `be93cfa` | docs: add contribution guide, security policy, citation metadata, and env template |
| `4a423f4` | chore: ignore Python artifacts, secrets, and personal/generated data files |
| `518d771` | fix: correct stale `parse_claims.py` reference in usage comment |
| `5a09f59` | chore: update `.aii` sidecar description and metadata date |
| `02da58a` | docs: fix markdown anchors to match GitHub heading slugification |
| *(this commit)* | docs: add review log and scoped TO-DO backlog |

Notes on scope discipline:

- The only code change is the usage-comment fix in `parse_fourthought.py`
  (doc/code drift). No runtime behavior was altered; `iris_apparently.py` and
  `hindsight.py` were documented, not changed.
- No tests exist to run; the heavy toolchains (tensorflow, legacy openai,
  discord) were not installed or executed, so no runtime verification of the
  scripts was attempted or claimed.

## Phase 4 — Final verification

- **Links/anchors:** a script checked every relative markdown link and
  heading anchor (GitHub slugification) across all `.md` files; all resolve.
- **Syntax:** `ast.parse` on all six `.py` files passes (unchanged from
  Phase 0; only a comment was edited).
- **Diff hygiene:** `git status` contains only intended files (see report);
  no pre-existing uncommitted changes were present at start.
- **Push:** `git push origin master` — verified `master` is up to date with
  `origin/master`.

## Deferred (see TO-DO.md "Open / deferred")

- O1 repair `iris_apparently.py`; O2 CI/lint workflow; O3 `openai >= 1.0`
  migration; O4 `hindsight.py` main-block cleanup; O5 CRLF data endings.
  Each is a code or toolchain change beyond this documentation pass, or
  deliberately left to avoid churn.

---

## Follow-up pass (2026-08-02) — deferred items implemented

On request, all five deferred items were implemented. Commits (chronological):

| Commit | Change |
| --- | --- |
| `1219457` | fix: add legacy OpenAI API shim (`openai_legacy.py` + 3 scripts) — O3 |
| `c7226c2` | refactor: hindsight pipeline as argparse CLI, guard imports — O4 |
| `513cdab` | fix: repair `iris_apparently.py` (imports, `main()` guard, fit/call reconciliation) — O1 |
| `11a2550` | ci: GitHub Actions checks (syntax, markdown links, shim smoke test) — O2 |
| `f18f219` | chore: normalize data CSV line endings to LF via `.gitattributes` — O5 |
| *(this commit)* | docs: update README/ARCHITECTURE/TO-DO for the follow-up pass |

Verification performed (real runs, no fabricated results):

- **O3 shim** — tested against a fake `openai` module: v1-style patch path
  (Completion/ChatCompletion callable, `error.RateLimitError` /
  `error.Timeout` / `error.InvalidRequestError` mapped), idempotency, and the
  pre-1.0 no-op path. All assertions passed.
- **O4 hindsight CLI** — imported with stubbed `pandas`/`openai`: module
  import has no side effects; `main([])` prints usage and returns; `--help`
  exits 0; unknown flag exits 2; all pipeline stage functions present.
- **O1 iris_apparently** — repaired, then runtime-tested against real
  TensorFlow 2.x (uv venv, Python 3.12, `tensorflow` + `pandas` +
  `scikit-learn`): module import OK; mask shapes OK; tiny-model forward pass
  OK; one `fit` step OK; no-source/no-temporal fallback OK; `main()`
  preprocessing glue (tokenizer, sinusoidal embeddings, `pad_sequences`,
  `train_test_split` on numpy) OK; full model configuration (d_model=512,
  num_layers=6, vocab=30000) forward pass OK. The runtime test surfaced three
  real bugs fixed during the pass: Keras sub-layer calls must use keyword
  arguments; source/cross attention was oriented wrong (query must be the
  sequence); `create_sinusoidal_embeddings` broadcast a (6, 256) array into a
  (256,) slice. `train_test_split` on TF tensors was also rejected by sklearn
  and now runs on numpy arrays.
- **O2 CI** — `scripts/check_markdown_links.py` run locally: 8 markdown
  files, all links/anchors OK; workflow YAML validated.
- **O5 line endings** — index blobs compared to HEAD: byte-identical after
  stripping `\r` (semantic-iris.csv 1103 CRs, chat-iris.csv 1502 CRs removed);
  row counts unchanged (1,478 / 2,414).

Not performed (stated honestly): no real OpenAI API calls (no credentials,
retired model IDs); no full `iris_apparently.py` training run (no
`text, source_id, timestamp` dataset in the repo); CI has not executed on
GitHub yet (first run will happen on the next push after this one).

---

## Follow-up pass 3 (2026-08-02) — OpenRouter migration

On request, all model calls were migrated from the retired OpenAI fine-tuned
`davinci` endpoints to OpenRouter (`https://openrouter.ai/api/v1`). Commits:

| Commit | Change |
| --- | --- |
| `a46c00e` | fix: migrate model calls to OpenRouter (shim routing, legacy completions emulated as chat, model slots remapped, OpenRouter attribution headers) |
| `6945d2f` | ci: verify script model IDs against the live OpenRouter catalog (`scripts/check_openrouter_models.py`) |
| `fcbd13e` | docs: document OpenRouter routing (README, ARCHITECTURE, SECURITY, CONTRIBUTING, DATA, `.env.example`) |
| `3c3b0e1` | fix: guard `openai_legacy.patch()` against openai >= 1.0 removed-API proxies |
| *(this commit)* | docs: record OpenRouter migration and CI outcomes in TO-DO/review log |

Grounded facts: `GET https://openrouter.ai/api/v1/models` is public (337
models at check time); `openai/gpt-4o-mini` and `openai/gpt-4o` verified in
the live catalog; OpenRouter docs confirm the OpenAI-SDK-compatible base URL,
`OPENROUTER_API_KEY` auth, and `HTTP-Referer` / `X-OpenRouter-Title`
attribution headers.

Verification performed (real runs):

- **Shim behavior (stub-based, 7 groups):** client constructed with
  `base_url=https://openrouter.ai/api/v1`, key from `OPENROUTER_API_KEY` with
  `OPENAI_API_KEY` fallback, attribution headers set; `Completion.create`
  translates `prompt` → chat `messages` (prompt arrays joined); responses
  support both `response['choices'][0]['text']` and
  `response.choices[0].text`; `ChatCompletion.create` passes through;
  pre-1.0 no-op path preserved.
- **Stub imports of all three scripts** with the migrated code: side-effect
  free (hindsight CLI usage/exit codes), shim patch executes, and no legacy
  model strings (`davinci:ft*`, `text-davinci*`, `gpt-3.5-turbo`, `"gpt-4"`)
  remain anywhere in the scripts.
- **Live OpenRouter catalog check** (`scripts/check_openrouter_models.py`):
  both model IDs present in the live catalog — exit 0.
- **GitHub CI (real, authoritative for the real-openai path):** the first two
  runs (30773591288, 30774785267) FAILED and surfaced a real bug: openai
  2.52.0 exposes `openai.Completion`/`ChatCompletion` as `APIRemovedInV1Proxy`
  deprecation shims, defeating the shim's `hasattr()` no-op guard. Fixed in
  `3c3b0e1` (version-gated guard with proxy-type fallback; five guard cases
  tested locally). Run `30775146930` on current `master` is **green**: all 8
  steps pass, including the live catalog check and the shim smoke test
  against real openai.

Not performed (stated honestly): live model calls still require an
`OPENROUTER_API_KEY` and the personal-archive inputs, neither of which is
available here; a full `iris_apparently.py` training run still lacks a
`text, source_id, timestamp` dataset.
