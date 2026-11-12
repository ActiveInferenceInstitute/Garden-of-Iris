# Publishing — Garden-of-Iris member

The [Publishing group contract](https://github.com/ActiveInferenceInstitute/ActiveInferenceJournal/blob/main/docs/workflows/publishing.md)
in ActiveInferenceJournal is authoritative. This page records this member's
bindings and pinned copies; it does not redefine the contract or record grammar.

## Member bindings

| Fact | Source-owned value |
| --- | --- |
| Gate entry point | `python scripts/gate.py <arm>` |
| Arms | `syntax docs fast tests models gnn` |
| Docs index | [docs/documentation-index.md](../documentation-index.md) |
| Manuscript command | none |
| GNN pin | [.github/gnn-pin.json](../../.github/gnn-pin.json) |

[`.aii/config.yaml`](../../.aii/config.yaml) records a task for each documented
arm command. Network-dependent `models` and `gnn` remain named, but the migration
checks run offline through `docs` and `tests`; no lead corpus arm is adopted.

## Canonical concerns

| Concern | Canonical copy | Member use |
| --- | --- | --- |
| Gate registry | [cli.py](../../scripts/gate/cli.py) | Pinned canonical module; the member's existing arm registry remains in `scripts/gate.py`, as required by its member row. |
| Links and anchors | [arm_docs.py](../../scripts/gate/arm_docs.py) | `scripts/check_markdown_links.py` delegates to `check_links`; the private link grammar is removed. |
| Docs-index coverage | [arm_docs.py](../../scripts/gate/arm_docs.py) | The same adapter invokes `check_docs_index`. |
| Measurements and generated Markdown | [arm_bench.py](../../scripts/gate/arm_bench.py) | Pinned canonical module and import dependency of `arm_docs.py`; the existing member report/freshness check remains authoritative for its own arms and receipts. |
| GNN pin | [gnn-pin.json](../../.github/gnn-pin.json) | Byte-identical canonical pin; the existing `gnn` arm already checks the member's parser and sketches. |

The contract says to keep checks the member already proves rather than duplicate
them. The lead's dispatcher, benchmark and corpus-specific checks are not exposed
as member commands. `cli.py`, `arm_bench.py` and
[common.py](../../scripts/gate/common.py) are unchanged dependencies of the canonical
docs module, not another member gate. The adapter preserves the member's Markdown
scope (including new files, excluding dependency/cache directories).

## Identity and drift checks

Identity rules come only from the unchanged
[record-identity.schema.json](record-identity.schema.json), not a prose mirror.
[identity.py](../../scripts/gate/identity.py) is the lead's stdlib-only checker;
[identity_selftest.py](../../scripts/gate/identity_selftest.py) exercises acceptance
of a matching Python copy and rejection of a diverged copy.

Every copied artifact below is pinned by its actual SHA-256:

```text
record-identity.schema.json  84f6c4df6efc3f15f0d8a9a05c8aabd0cbdc08b0f4feac5fcc8ae860a81e306b
identity.py  847328ff163fa90c869495164869caf4e83313748e8a444dbab8d4e459b11074
identity_selftest.py  bf029061b62c0b1d0275d71126fc7f962242ee7d32847958dc481fc2877fbe49
arm_docs.py  08a83f132ce9b36cd538a8ace8bf718c1eefd2d6a3f2747baa6f10c1af6ccfaf
arm_bench.py  188e620cbb0ba5f5c124c5390b4d2089642956166ed1a115947666b933097017
cli.py  4930bfce0fb9a4cfa4746f98b63bde83cc7fe6957bbe1e832b30644a3e2d7872
common.py  ccf0e56d1a9466e3690ace00a6afbef570813762e889cd03cd470c7576753880
gnn-pin.json  eb83f7f1b73eb31e116bd05b1f457dd07e6874a2a4ba0e9e95e5bc91f094cd55
```

`python scripts/gate.py docs` checks the schema and complete digest block, runs
`python scripts/gate/identity.py --verify-copy <copy>` through the canonical
module's `main` for every listed copy, runs its drift selftest, then checks links,
index coverage and the existing generated facts. The contract's direct checks
also work from the repository root:

```bash
python scripts/gate/identity.py --verify-copy docs/workflows/record-identity.schema.json
python scripts/gate/identity.py --verify-copy scripts/gate/identity.py
```

This migration makes no claim about a Journal corpus in Garden-of-Iris: no
`INDEX.json`, record metadata, manuscript, or model results are manufactured.
The member's training CSVs are not Publishing records. Updates to canonical
copies require copying the source bytes and updating their digests together;
never edit the vendored schema or Python modules independently.
