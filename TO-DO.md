# TO-DO

Last reviewed: 2026-11-12 — checked against `master` at `354dc4e` and its
last 20 commits. Earlier verification is recorded in
[REVIEW_LOG_2026-08-02.md](REVIEW_LOG_2026-08-02.md).

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

- [x] **D1 — Required environment variables undocumented.** `.env.example`
  provides empty placeholders for `OPENROUTER_API_KEY`, fallback
  `OPENAI_API_KEY`, `DISCORD_BOT_KEY`, and `AIRTABLE_API_KEY`.
  ✓ `be93cfa`, `fcbd13e`
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
- [x] **D5 — Experimental/legacy status undocumented.** README and
  `docs/ARCHITECTURE.md` document the current SDK client, retired fine-tuned
  model IDs, and hardcoded Discord channel IDs. ✓ `43e4fe4`, `25723da`
- [x] **D6 — Non-runnable sketch unlabeled.** `docs/ARCHITECTURE.md`
  records the repaired imports, ordering, and training-call interface in
  `iris_apparently.py`, and explicitly distinguishes that repair from a
  full training run. ✓ `43e4fe4`, `513cdab`

## Minor

- [x] **N1 — Data files undocumented.** Schemas, row counts, and provenance
  added in `docs/DATA.md`; CSV line endings are now LF.
  ✓ `43e4fe4`, `f18f219`
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
- **O2 (Major) — CI/lint workflow** — **COMPLETED** `11a2550`, `abde7ad`:
  `.github/workflows/ci.yml` invokes the shared `scripts/gate.py` arms for
  syntax, docs, tests, model catalog, and pinned GNN conformance. This records
  implemented checks, not a claim that hosted CI is currently green.
- **O3 (Medium) — Migrate to the current OpenAI SDK API** — **COMPLETED**
  `64f062b`: `iris_llm.py` replaced the interim `1219457` compatibility shim;
  all three model-calling scripts use its current chat-completions helpers.
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

- `iris_llm.py` now routes every request through OpenRouter: the client is
  built with `base_url=https://openrouter.ai/api/v1`, the key comes from
  `OPENROUTER_API_KEY` (fallback `OPENAI_API_KEY`), and OpenRouter attribution
  headers (`HTTP-Referer`, `X-OpenRouter-Title`) are set. `complete()` sends a
  prompt as a user message; `chat_completion()` returns the SDK response.
  The initial routing landed in `a46c00e`; `64f062b` removed
  `openai_legacy.py` and its response wrappers.
- The retired fine-tuned `davinci` model slots in `discord_bot.py` and
  `parse_fourthought.py` now map to catalog-verified OpenRouter chat models
  (`openai/gpt-4o-mini`, `openai/gpt-4o`); `hindsight.py` uses the same
  default. `scripts/check_openrouter_models.py` verifies every model ID the
  scripts use against the live catalog (CI step). Commit: `6945d2f`.
- Docs (README, ARCHITECTURE, SECURITY, CONTRIBUTING, DATA, docs index) and
  `.env.example` updated for `OPENROUTER_API_KEY`. Commit: `fcbd13e`.

### Still open

- **Full training run of `iris_apparently.py`.** Blocked outside this
  repository on a CSV with `text, source_id, timestamp` columns; neither
  tracked CSV has this schema (see `docs/DATA.md`). Owner: Iris research/data
  steward to supply an authorized dataset; model maintainer to run training
  and record results once it exists.
- **Real end-to-end runs of the OpenRouter-backed scripts** (`discord_bot.py`,
  `hindsight.py`, `parse_fourthought.py`). Blocked outside this repository on
  `OPENROUTER_API_KEY`, personal-archive inputs, and Discord/Airtable access
  where used (`AGENTS.md`, `.env.example`). Owner: archive/service operator
  to provision authorized inputs and credentials; script maintainer to
  exercise the real integrations and record results. Stubbed unit tests and
  a catalog check do not prove a live run.
- **Restore hosted CI availability.** GitHub Actions is billing-locked
  org-wide; historical green run `30775146930` is not current evidence.
  Blocked outside this repository. Owner: Institute organization billing
  administrator to restore Actions, then repository maintainer to rerun
  `.github/workflows/ci.yml`; local gate evidence remains separate.
- **Update the pinned GNN parser.** `.github/gnn-pin.json` still selects
  `v5.0.3` at `8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1`, not released
  `v5.1.0` at `75c834bd8519dc7b5adc4d24f16bf393cfd1ecdf`. Owner: repository
  maintainer, coordinating with the Publishing contract owner because
  `docs/workflows/publishing.md` digest-pins the canonical copy. Blocked on
  that coordinated pin/digest update and conformance verification, not on
  authored GNN content: this repository has no model sketch.
- **Resolve the eight planned hindsight functions.** `hindsight.py`'s
  `create_yearly_summaries` through `create_trackable_summaries` remain
  `pass` bodies; documenting them under N2 did not implement them.
  Owner: hindsight maintainer to decide which planned outputs are supported,
  then implement and test those functions or remove unused declarations and
  update `docs/ARCHITECTURE.md`. Blocked on that scope/output decision and
  the missing implementations, not on hosted CI.

## Current-API and GNN-alignment pass (2026-11-01)

Scope: replace the legacy compatibility shim with the current supported API,
add a test suite and CI coverage for it, and signpost the fleet's GNN
specification core. Findings and verification are recorded in
[REVIEW_LOG_2026-08-02.md](REVIEW_LOG_2026-08-02.md) (pass 4).

- [x] **Legacy shim removed.** `openai_legacy.py` (pre-1.0 API emulation) is
  deleted; `iris_llm.py` is the single home for model calls on the current
  `openai` SDK surface, routed through OpenRouter. `discord_bot.py`,
  `hindsight.py`, and `parse_fourthought.py` call `iris_llm.chat()` /
  `complete()` / `chat_completion()` directly; retries use the SDK's
  `RateLimitError` / `APITimeoutError` instead of the removed `openai.error`
  namespace. ✓ `64f062b`
- [x] **PDF dependency current.** `parse_fourthought.py` reads PDFs with
  `pypdf` (the maintained successor) instead of `PyPDF2`, whose
  `PyPDF2.utils.PdfReadError` path no longer exists in current releases.
  ✓ `64f062b`
- [x] **Import-safe scripts.** `parse_fourthought.py`, `twitter_archive.py`,
  and `text_process.py` do their work in functions behind `main()`, so
  importing them has no side effects and the helpers are testable.
  ✓ `64f062b`
- [x] **Tests and CI wiring.** `tests/` covers the client (stubbed SDK), the
  parser helpers and model loop, the hindsight summary call and CLI, the data
  tools, and a guard that no legacy API surface returns. The workflow invokes
  the test and other gate arms; no hosted-run success is implied.
  ✓ `5752247`, `abde7ad`
- [x] **Dependency manifests.** `requirements.txt` (component set) and
  `requirements-dev.txt` (tests/CI) now require `openai>=3.45.0`.
  Neither declares `inferactively-pymdp`; there is no 1.0.5 adoption to mark
  done or a pymdp runtime to upgrade here. ✓ `5752247`, `cdbb507` (#7)
- [x] **GNN signposting.** `README.md` and the new `AGENTS.md` link the GNN
  integration and implementation guides and the related fleet repositories
  (active_inference_language_model, courses, Active_Inference_Ontology).
  Garden-of-Iris itself specifies no Active Inference generative model
  (FourThought typing is prompt-driven; the Iris LM is a neural sketch), so no
  `.gnn.md` file was forced; the README records the condition under which one
  would be added. ✓ `25723da`

## Gate and Publishing updates (2026-11-12)

- [x] **Canonical GNN pin schema.** `.github/gnn-pin.json` declares
  `gnn-importer-pin/v1`; the parser remains at `v5.0.3`. This is not the
  `v5.1.0` GNN–FEP cutover. ✓ `a2ad766` (#9)
- [x] **One gate entry point and documentation hub.** `scripts/gate.py`
  exposes separately runnable arms; `docs/README.md`,
  `docs/documentation-index.md`, and `docs/RUN_GUIDE.md` describe them.
  ✓ `abde7ad` (#10)
- [x] **Measured gate receipts.** `docs/_generated/gate-before.json` and
  `gate-after.json` feed `docs/_generated/GATES.md`; `report --check`
  checks generated facts and receipt-command drift. ✓ `39b8315` (#11)
- [x] **Publishing contract migration.** `docs/workflows/publishing.md`
  records the canonical schema/module digests;
  `scripts/check_markdown_links.py` delegates identity, links, and index
  coverage checks to the pinned sources. No Journal corpus is claimed.
  ✓ `28655bc` (#12)
- [x] **Sidecar documentation paths.** `.aii/config.yaml` uses
  sidecar-relative paths and its generated guides were refreshed.
  ✓ `354dc4e` (#13)
