# Security

## Reporting a vulnerability

If you discover a security issue in this repository, please report it
privately to the Active Inference Institute rather than opening a public
issue. GitHub's private security advisory workflow on this repository is the
preferred channel; alternatively, contact the institute at
security@activeinference.institute (do not include secrets in the subject
line).

## Secret handling

This repository must never contain credentials. The scripts read all secrets
from environment variables:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API access |
| `DISCORD_BOT_KEY` | Discord bot token |
| `AIRTABLE_API_KEY` | Airtable API access |

- Add secrets to your environment or a local `.env` file — never to
  committed files. `.env` is ignored by `.gitignore`.
- If a secret is accidentally committed, rotate it immediately and rewrite
  the commit history.
- The legacy OpenAI calls in this codebase use the pre-1.0 `openai` package;
  see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#caveats) for notes.

## Data sensitivity

The scripts expect personal thought archives as inputs
(`prophet_thought_dump_ALL_THOUGHTS_2023.csv`, `data/tweets.js`). These files
are private and are covered by `.gitignore`; do not commit them or include
their contents in issues, pull requests, or documentation.

## Scope

This is an experimental research repository with no deployed service
surface. The Discord bot, when run, requires a valid Discord token and
guild permissions; run it only in servers you control.
