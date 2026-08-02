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
