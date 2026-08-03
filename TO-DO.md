# TO-DO

Last reviewed: 2026-08-02 — documentation-deep review pass (see
[REVIEW_LOG_2026-08-02.md](REVIEW_LOG_2026-08-02.md)).

Sections are defined as:

- **Minor** — typo, broken link, formatting, single-file cosmetics.
- **Medium** — stale section rewrite, doc restructure, added missing guide or
  metadata file.
- **Major** — large doc system overhaul, new documentation site, cross-cutting
  refactors.

## Major

- [x] **M1 — No README for a public repo.** Write a root README: what the
  project is, repository layout, quick start, requirements, environment
  variables, license. `README.md` ✓ `2b3f778`
- [x] **M2 — No documentation system at all.** Create a `docs/` folder with an
  index, a component/architecture overview, and a data reference.
  `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/DATA.md` ✓ `43e4fe4`
- [x] **M3 — Missing contribution, security, and citation metadata.** Add
  `CONTRIBUTING.md`, `SECURITY.md`, and `CITATION.cff`. ✓ `be93cfa`

## Medium

- [x] **D1 — Required environment variables undocumented.** Add
  `.env.example` with empty placeholders for `OPENAI_API_KEY`,
  `DISCORD_BOT_KEY`, `AIRTABLE_API_KEY`. ✓ `be93cfa`
- [x] **D2 — No `.gitignore`.** Python artifacts (`__pycache__`, `*.pyc`),
  secrets (`.env`), personal archives (`data/tweets.js`,
  `prophet_thought_dump_ALL_THOUGHTS_2023.csv`, `tarot_text.csv`), and
  script-generated CSVs were at risk of accidental commit. ✓ `4a423f4`
- [x] **D3 — Doc/code drift: stale script name in usage comment.**
  `parse_fourthought.py` referenced the removed `parse_claims.py`.
  `parse_fourthought.py` ✓ `518d771`
- [x] **D4 — Generic sidecar description.** `.aii/config.yaml` described the
  repo as a placeholder; replaced with an accurate one-liner and bumped
  `meta.updated`. ✓ `5a09f59`
- [x] **D5 — Experimental/legacy status undocumented.** Legacy OpenAI API
  (`openai < 1.0`), retired fine-tuned model IDs, and hardcoded Discord
  channel IDs now documented in README and `docs/ARCHITECTURE.md#caveats`.
  ✓ `43e4fe4`
- [x] **D6 — Non-runnable sketch unlabeled.** `iris_apparently.py` blockers
  (missing `layers` import, module-level ordering `NameError`s, `fit`
  signature mismatch, unused helpers) documented explicitly.
  `docs/ARCHITECTURE.md` ✓ `43e4fe4`

## Minor

- [x] **N1 — Data files undocumented.** Schemas, row counts, CRLF line
  endings, and provenance added in `docs/DATA.md`. ✓ `43e4fe4`
- [x] **N2 — Undocumented stub functions.** The eight `pass`-body functions in
  `hindsight.py` are now listed as planned work in
  `docs/ARCHITECTURE.md`. ✓ `43e4fe4`
- [x] **N3 — Broken markdown anchors.** Hand-written heading fragments did not
  match GitHub slugification (`#iris_apparentlypy`,
  `#data-semantic-iriscsv`, etc.); corrected and verified by script.
  `README.md`, `docs/ARCHITECTURE.md` ✓ `02da58a`

## Follow-up pass — deferred items resolved (2026-08-02)

The items below were originally deferred from the documentation pass and were
implemented on request in a follow-up pass. Verification notes for each are in
[REVIEW_LOG_2026-08-02.md](REVIEW_LOG_2026-08-02.md).

- **O1 (Major) — Repair `iris_apparently.py`** — **COMPLETED** `513cdab`:
  missing `layers` import added, module-level training block moved into
  `main()` under a `__main__` guard, and `DemocraticLLM` reconciled with the
  documented `fit` call. Runtime-verified against TensorFlow 2.x / Python
  3.12 (import, masks, forward pass, one `fit` step, no-source fallback,
  `main()` preprocessing glue, full-config forward). A full training run
  remains out of reach because no `text, source_id, timestamp` dataset is
  committed.
- **O2 (Major) — CI/lint workflow** — **COMPLETED** `11a2550`: GitHub Actions
  with a Python syntax check, the markdown link/anchor checker, and an
  `openai >= 1.0` shim smoke test.
- **O3 (Medium) — Migrate to `openai >= 1.0` API surface** — **COMPLETED**
  `1219457`: `openai_legacy.py` shim patches `openai.Completion` /
  `openai.ChatCompletion` / `openai.error.*` onto the 1.x client API; no-op on
  pre-1.0 installs. Verified against a fake 1.x module (patch path, exception
  mapping, idempotency, pre-1.0 no-op path).
- **O4 (Medium) — `hindsight.py` main block cleanup** — **COMPLETED**
  `c7226c2`: single FourThought load, argparse CLI (`--daily` … `--all`),
  import is side-effect free. CLI wiring verified with stubbed `pandas` /
  `openai`.
- **O5 (Minor) — CRLF line endings in `data/*.csv`** — **COMPLETED**
  `f18f219`: `.gitattributes` (`* text=auto`, `eol=lf` for py/md/csv/yaml/yml/
  cff) plus `git add --renormalize`; index blobs verified byte-identical to
  HEAD after stripping `\r`.

## OpenRouter migration (2026-08-02)

On request, all model calls were migrated from the retired OpenAI fine-tuned
`davinci` endpoints to **OpenRouter** (`https://openrouter.ai/api/v1`):

- `openai_legacy.py` routes every request through OpenRouter: the client is
  built with `base_url=https://openrouter.ai/api/v1`, the key comes from
  `OPENROUTER_API_KEY` (fallback `OPENAI_API_KEY`), and OpenRouter attribution
  headers (`HTTP-Referer`, `X-OpenRouter-Title`) are set. Legacy
  `Completion.create(prompt=...)` is emulated as a chat completion (OpenRouter
  has no `/completions` endpoint), and responses are wrapped so both legacy
  access styles work (`response.choices[0].text` and
  `response['choices'][0]['text']`). Commits: `a46c00e`, `3c3b0e1`.
- The retired fine-tuned `davinci` model slots in `discord_bot.py` and
  `parse_fourthought.py` now map to catalog-verified OpenRouter chat models
  (`openai/gpt-4o-mini`, `openai/gpt-4o`); `hindsight.py` uses the same
  default. `scripts/check_openrouter_models.py` verifies every model ID the
  scripts use against the live catalog (CI step). Commit: `6945d2f`.
- Docs (README, ARCHITECTURE, SECURITY, CONTRIBUTING, DATA, docs index) and
  `.env.example` updated for `OPENROUTER_API_KEY`. Commit: `fcbd13e`.
- A real bug was found by the first GitHub CI run and fixed (`3c3b0e1`):
  openai >= 1.0 exposes `openai.Completion` / `openai.ChatCompletion` only as
  `APIRemovedInV1Proxy` deprecation shims, which defeated the old `hasattr()`
  no-op guard; the guard is now version-gated with a proxy-type fallback.

### Still open

- **Full training run of `iris_apparently.py`.** Requires a CSV with `text,
  source_id, timestamp` columns; no such dataset exists in the repository.
- **Real end-to-end runs of the OpenAI-backed scripts** (`discord_bot.py`,
  `hindsight.py`, `parse_fourthought.py`). Request plumbing (client wiring,
  prompt→messages translation, response shapes, model IDs) is verified, but a
  live run still requires an `OPENROUTER_API_KEY` and the personal-archive
  inputs, which are not committed.
- **CI status: PASSING on GitHub.** Workflow `ci.yml` runs on every push.
  Runs `30773591288` and `30774785267` failed on the openai 2.x proxy bug
  (fixed in `3c3b0e1`); run `30775146930` (current `master`) is green — all
  8 steps, including the live OpenRouter catalog check and the shim smoke
  test against real `openai`.
