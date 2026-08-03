# Garden-of-Iris — Documentation

This is the documentation index for the Garden-of-Iris repository. The project
is an experimental toolkit for **Iris**, a collective-intelligence language
model, and the data pipeline that supports it. Start with the
[README](../README.md) for a high-level orientation.

## Index

| Document | Purpose |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component-by-component overview of every script, the data flow between them, and the FourThought dialectic |
| [DATA.md](DATA.md) | All data files: tracked training data, expected inputs, and generated outputs, with column schemas |

## Related top-level files

- [README.md](../README.md) — quick start, requirements, environment variables, license
- [CONTRIBUTING.md](../CONTRIBUTING.md) — contribution guidelines
- [SECURITY.md](../SECURITY.md) — security notes and secret handling
- [CITATION.cff](../CITATION.cff) — citation metadata
- [TO-DO.md](../TO-DO.md) — review findings and improvement backlog
- [LICENSE](../LICENSE) — CC BY 4.0 license text

## Component quick reference

| Script | One-liner |
| --- | --- |
| `discord_bot.py` | Discord bot "Iris": auto-summarizing pools, DM relay, slash commands |
| `hindsight.py` | Hindsight summarization pipeline (daily → weekly → monthly) + training-data construction |
| `parse_fourthought.py` | CLI that parses a URL or PDF into FourThought thought types |
| `iris_apparently.py` | Repaired TensorFlow "DemocraticLLM" transformer sketch (source + temporal embeddings); smoke-tested, not trained |
| `openai_legacy.py` | Compatibility shim: legacy `openai.Completion` / `ChatCompletion` calls routed through OpenRouter |
| `twitter_archive.py` | Converts a Twitter archive export to CSV |
| `text_process.py` | Builds prompt→completion sentence pairs with NLTK |

## Conventions

- Documentation is written in Markdown (GFM), one space per sentence, tables
  for schemas, and relative links only.
- Data files are documented in [DATA.md](DATA.md) with their exact column
  names as read by the code.
- Claims about script behavior are grounded in the source; when a script is a
  non-runnable sketch (e.g. `iris_apparently.py`), that is stated explicitly
  in [ARCHITECTURE.md](ARCHITECTURE.md) rather than implied.
