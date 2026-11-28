# Methods

The review followed the command entry points, parsers and verification documentation at the version cited below. `discord_bot.py` contains the interactive collection surface. `parse_fourthought.py` accepts outside text as a transformation input, and `hindsight.py` aggregates tagged historical material into summaries and fine-tuning-oriented structures. The architecture guide distinguishes these applications from `iris_llm.py`, which centralises access to model APIs. This separation lets a reader distinguish deterministic handling of the input record from an externally generated response.

The unit of comparison was the source interface together with the declared dependencies and artifacts. No external model calls, training runs or Discord interactions were used as evidence. Historical model endpoints and local paths are treated as constraints on replaying the original experiments.
