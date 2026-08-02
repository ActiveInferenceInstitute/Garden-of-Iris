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

## Open / deferred

- **O1 (Major) — Repair `iris_apparently.py`.** Add the missing `layers`
  import, fix module-level call ordering, and reconcile the `fit` call with
  `DemocraticLLM.call`. *Deferred:* code change beyond a documentation pass;
  the file is an intentionally unfinished sketch, and its behavior is
  documented rather than altered.
- **O2 (Major) — CI/lint workflow.** No `.github/` exists; adding one would
  introduce a new toolchain. *Deferred:* out of scope for this pass (no
  heavyweight toolchains for docs).
- **O3 (Medium) — Migrate to `openai >= 1.0` API surface.** All scripts use
  `openai.Completion` / `openai.ChatCompletion`. *Deferred:* code migration
  with behavioral risk; legacy status documented in `docs/ARCHITECTURE.md`.
- **O4 (Medium) — `hindsight.py` main block cleanup.** Loads the same CSV
  twice, and only `construct_monthly_training_data()` executes (summarization
  is commented out). *Deferred:* code refactor, out of scope for this pass.
- **O5 (Minor) — CRLF line endings in `data/*.csv`.** Left as-is: data files,
  not documentation; converting them would churn tracked content.
