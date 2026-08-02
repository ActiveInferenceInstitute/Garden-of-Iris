# Contributing

Thanks for your interest in Garden-of-Iris! This is an experimental,
research-oriented repository stewarded by the Active Inference Institute, and
all contributions are published publicly.

## Ground rules

- **No secrets.** The repository is public. Never commit API keys, bot
  tokens, or personal archives. The scripts read credentials from environment
  variables (`OPENAI_API_KEY`, `DISCORD_BOT_KEY`, `AIRTABLE_API_KEY`); see
  [.env.example](.env.example) for the shape of these variables.
- **No personal data.** Untracked inputs such as
  `prophet_thought_dump_ALL_THOUGHTS_2023.csv`, `data/tweets.js`, and
  `tarot_text.csv` are private archives — do not add them to git (they are
  already covered by `.gitignore`).
- **Match reality.** Documentation and comments must describe what the code
  actually does. If a claim in the docs is wrong relative to the source, fix
  the claim.
- **Small, focused changes.** Keep commits scoped and message them clearly
  (e.g. `docs: ...`, `fix: ...`).

## How to contribute

1. Fork the repository (or work on a branch of `master`).
2. Make your change, keeping the existing style.
3. Verify: markdown changes should keep relative links valid; Python changes
   should at least parse (`python -m py_compile <file>`).
4. Open a pull request against `master` describing what you changed and why.

## Reviewing documentation

If you edit `docs/` or this file:

- Prefer relative links between repository files.
- Keep table columns aligned with the actual CSV/JSON schemas (see
  [docs/DATA.md](docs/DATA.md)).
- State clearly when a script is a non-runnable sketch rather than implying
  it works (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

## License

By contributing you agree that your contributions are licensed under the
repository's [CC BY 4.0](LICENSE) license.
