# Garden-of-Iris — Documentation

**Documentation hub.** This is the entry point for the documentation tree; the
flat, complete list of long-lived documents is
[documentation-index.md](documentation-index.md). Start with the
[README](../README.md) for a high-level orientation to the project, an
experimental toolkit for **Iris** — a collective-intelligence language model —
and the data pipeline that supports it.

## Navigation

| Need | Document |
| --- | --- |
| Run the checks (one entry point, one command per arm) | [RUN_GUIDE.md](RUN_GUIDE.md) |
| Understand the components and the data flow | [ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| Know every data file, its columns, and its provenance | [DATA.md](architecture/DATA.md) |
| Find any long-lived document | [documentation-index.md](documentation-index.md) |
| Read the current generated facts | [_generated/GATES.md](_generated/GATES.md) |

```mermaid
graph TD
    README[README.md<br/>project overview]
    HUB[docs/README.md<br/>this hub]
    INDEX[documentation-index.md<br/>flat index]
    RUN[RUN_GUIDE.md<br/>gate and CI]
    ARCH[ARCHITECTURE.md<br/>components]
    DATA[DATA.md<br/>data files]
    GATES[_generated/GATES.md<br/>arms, tests, runtimes]

    README --> HUB
    HUB --> INDEX
    HUB --> RUN
    HUB --> ARCH
    HUB --> DATA
    RUN --> GATES
```

## Gate and CI in one paragraph

`scripts/gate.py` is the only gate entry point. Its arms are `syntax`, `docs`,
`fast`, `tests`, `models`, and `gnn`; the default arm is `fast`, and CI's job
key `checks` (display name `checks`) runs `syntax`, `docs`, `tests`, and
`models`, while job key `gnn-conformance` (display name
`gnn conformance (pinned)`) runs `gnn`. The GNN pin is
[`.github/gnn-pin.json`](../.github/gnn-pin.json) — schema
`gnn-importer-pin/v1`, `ActiveInferenceInstitute/Generalized_Notation_Notation`
at `v5.1.0` (`75c834bd8519dc7b5adc4d24f16bf393cfd1ecdf`) — and
[`.github/GNN.md`](../.github/GNN.md) records what the conformance arm parses.
Commands, per-arm prerequisites, and the hosted-CI caveat are in
[RUN_GUIDE.md](RUN_GUIDE.md).

## Evidence rules

Documentation is a view over source-owned facts, not a second place to keep
them.

| Claim type | Authoritative source | Rule |
| --- | --- | --- |
| Commands, defaults, CI steps | `scripts/gate.py`, `.github/workflows/ci.yml` | Run the arm; do not restate a command that the gate defines. |
| Arm runtimes, test counts | [`_generated/GATES.md`](_generated/GATES.md), rendered from the `measure` receipts | `measure --label before\|after` then `report`; never hand-edit a number. |
| The GNN pin | [`.github/gnn-pin.json`](../.github/gnn-pin.json) | Cite the revision from the pin file, not from an older guide. |
| Script behavior, data schemas | The source and [DATA.md](architecture/DATA.md) | State explicitly when a script is a non-runnable sketch. |

## Component quick reference

| Script | One-liner |
| --- | --- |
| `discord_bot.py` | Remote-model bot with `/`-prefixed commands; not a consumer of sketch weights |
| `hindsight.py` | Independently supplied archives → bound summaries and seeded prompt/completion pairs |
| `parse_fourthought.py` | Web/PDF text → printed thought/type pairs, not the hindsight input export |
| `iris_apparently.py` | Separate dataset and private-bundle neural sketch; historical smoke does not qualify current component changes |
| `iris_llm.py` | Validated first-choice helpers plus raw-response/all-choice interfaces |
| `twitter_archive.py` | Twitter JS → schema-preserving CSV consumed by hindsight |
| `text_process.py` | Independent sentence-pair builder |
| `tests/` | Core, optional components, gate and actual GNN admission controls; prerequisites are explicit |

## Conventions

- Documentation is written in Markdown (GFM), one space per sentence, tables
  for schemas, and relative links only.
- Data files are documented in [DATA.md](architecture/DATA.md) with their exact column names
  as read by the code.
- Claims about script behavior are grounded in the source; when a script is a
  non-runnable sketch (e.g. `iris_apparently.py`), that is stated explicitly in
  [ARCHITECTURE.md](architecture/ARCHITECTURE.md) rather than implied.
- Generated numbers live only in [_generated/](_generated/GATES.md); prose links
  there instead of copying a value.

## Research manuscript

- [FourThought as a Data Model for Community Language-Model Experiments](manuscript/README.md) — paper source and reproducible PDF build.

## Documentation areas

- [Architecture and data flow](architecture/README.md)
- [Running and verifying the toolkit](operations/README.md)
