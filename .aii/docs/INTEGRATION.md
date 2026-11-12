# InstituteOS integration — Garden-of-Iris

## Identity

| Field | Value |
| --- | --- |
| Repository | `ActiveInferenceInstitute/Garden-of-Iris` |
| Affiliation | `institute` |
| Category | `research` |
| Status | `active` |
| Maturity | `wip` |
| Steward | Active Inference Institute |
| Default branch | `master` |
| Current release | — |
| License | `CC-BY-4.0` |
| Citation | Active Inference Institute — Garden-of-Iris. |

## Federation

| Setting | Value |
| --- | --- |
| Dashboard mode | `repos` |
| Analytics | `true` |
| Dashboard | `true` |
| Sync policy | `pull` |
| Registries | — |
| Tags | garden-of-iris, collective-intelligence, language-model, pipeline |

## Ecosystem relations

| Repository | Relation | Note |
| --- | --- | --- |
| `ActiveInferenceInstitute/InstituteOS` | `referenced-by` | Federated via the InstituteOS .aii manifest. |
| `ActiveInferenceInstitute/Generalized_Notation_Notation` | `references` | Uses Generalized Notation Notation (GNN) for model specifications. |

## Key artifacts

| Path | Kind | Description |
| --- | --- | --- |
| `.` | `other` | Repository root. |
| `README.md` | `doc` | Repository overview. |
| `AGENTS.md` | `doc` | Agent guidance. |
| `LICENSE` | `doc` | License. |
| `CITATION.cff` | `citation` | Machine-readable citation metadata. |
| `tests` | `test` | Test suite. |
| `docs` | `doc` | Documentation tree. |

## Portable tasks

| Task | Command | Working directory | Description |
| --- | --- | --- | --- |
| `syntax` | `python scripts/gate.py syntax` | `.` | Compile every Python module. |
| `docs` | `python scripts/gate.py docs` | `.` | Check links, index coverage, publishing digests and generated facts. Docs index: docs/documentation-index.md. Manuscript command: none. |
| `fast` | `python scripts/gate.py fast` | `.` | Run the default offline unit suite. |
| `tests` | `python scripts/gate.py tests` | `.` | Run the whole Python test suite. |
| `models` | `python scripts/gate.py models` | `.` | Check model IDs against the live OpenRouter catalog (network). |
| `gnn` | `python scripts/gate.py gnn` | `.` | Run pinned GNN conformance (network, Python 3.12). Pin: .github/gnn-pin.json. |

## Validation

```bash
python -m aii_platform.aii_sidecar.validate <repo> --completeness
python -m aii_platform.aii_sidecar docs <repo> --overwrite
python -m aii_platform.aii_sidecar.run <repo> --list
```

The sidecar is valid when `validate` prints `OK` and reports no missing artifact,
manifest, link, or declared-doc path. Completeness is a curation target, not a
runtime requirement.

## Data boundary

This sidecar carries metadata only. It does not grant execution permission, does not
replace the repository's own documentation, and must not be used to move private
content into a public repository. Task execution is limited to trusted checkouts.
