#!/usr/bin/env python3
"""Verify that every model ID referenced by the scripts exists in the
OpenRouter catalog.

Fetches https://openrouter.ai/api/v1/models (a public endpoint) and checks
each ``openai/...`` model string found in ``discord_bot.py``, ``hindsight.py``,
and ``parse_fourthought.py``. Exits non-zero on missing models or network
failure.

Usage: python scripts/check_openrouter_models.py
"""

import json
import pathlib
import re
import sys
import urllib.request

CATALOG_URL = "https://openrouter.ai/api/v1/models"
SCRIPT_FILES = ["discord_bot.py", "hindsight.py", "parse_fourthought.py"]


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    model_ids = set()
    for name in SCRIPT_FILES:
        src = (root / name).read_text(encoding="utf-8")
        model_ids.update(re.findall(r"openai/[A-Za-z0-9._-]+", src))

    try:
        with urllib.request.urlopen(CATALOG_URL, timeout=30) as resp:
            catalog = {m["id"] for m in json.load(resp)["data"]}
    except Exception as exc:  # network failure -> hard fail (CI signal)
        print(f"ERROR: could not fetch OpenRouter catalog: {exc}", file=sys.stderr)
        return 1

    missing = sorted(model_ids - catalog)
    for model in sorted(model_ids):
        print(f"{model:40s} {'ok' if model in catalog else 'MISSING'}")
    if missing:
        print(f"ERROR: models not in OpenRouter catalog: {missing}", file=sys.stderr)
        return 1
    print(f"verified {len(model_ids)} model ID(s) against OpenRouter catalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
