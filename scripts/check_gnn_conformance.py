#!/usr/bin/env python3
"""Pinned GNN conformance check.

Reads `.github/gnn-pin.json` (schema `gnn-importer-pin/v1`), installs that exact
revision of Generalized_Notation_Notation, and verifies the installed parser:
every `*.gnn.md` sketch in the repository is parsed, syntax-checked, and
type-checked; when the repository has no sketch, the rejection baseline is the
pinned upstream `input/gnn_files/basics/static_perception.md` exemplar.

This module is the single implementation of the check. `python scripts/gate.py
gnn` and the `gnn-conformance` CI job both call it; the workflow holds no copy
of the parsing logic.

Usage:
    python scripts/check_gnn_conformance.py              # install + verify
    python scripts/check_gnn_conformance.py --no-install # verify only
    python scripts/check_gnn_conformance.py --no-verify  # install only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN_PATH = ROOT / ".github" / "gnn-pin.json"
PIN_SCHEMA = "gnn-importer-pin/v1"
PIN_REPOSITORY = "ActiveInferenceInstitute/Generalized_Notation_Notation"
RUNTIME_DEPENDENCIES = ("defusedxml", "psutil", "pyyaml")
EXEMPLAR_RELPATH = "input/gnn_files/basics/static_perception.md"
# Directories that never contain repository sketches: the installed parser and
# local caches must not change what "the repository's sketches" means.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


def load_pin(path: Path = PIN_PATH) -> dict:
    pin = json.loads(path.read_text(encoding="utf-8"))
    if pin.get("schema") != PIN_SCHEMA:
        raise SystemExit(f"{path}: expected schema {PIN_SCHEMA!r}, found {pin.get('schema')!r}")
    if pin.get("repository") != PIN_REPOSITORY:
        raise SystemExit(f"{path}: expected repository {PIN_REPOSITORY!r}, found {pin.get('repository')!r}")
    if not REVISION_RE.match(str(pin.get("revision", ""))):
        raise SystemExit(f"{path}: revision must be a 40-character lowercase commit id")
    if not str(pin.get("tag", "")).startswith("v"):
        raise SystemExit(f"{path}: tag must be a release tag such as 'v5.0.3'")
    return pin


def pip_install(*args: str) -> None:
    command = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *args]
    try:
        subprocess.check_call(command, cwd=ROOT, stdin=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        hint = ""
        if sys.version_info >= (3, 15):
            hint = (
                "\nhint: the pinned parser declares requires-python '>=3.11,<3.15'; "
                f"run this check with Python 3.12 (the CI pin), not {sys.version_info.major}.{sys.version_info.minor}"
            )
        raise SystemExit(f"pip install failed (exit {exc.returncode}){hint}") from exc


def install(pin: dict) -> str:
    pip_install(*RUNTIME_DEPENDENCIES)
    spec = f"generalized-notation-notation @ git+https://github.com/{pin['repository']}.git@{pin['revision']}"
    pip_install("--no-deps", spec)
    return spec


def repository_sketches() -> list[Path]:
    sketches = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        sketches.extend(Path(dirpath) / name for name in filenames if name.endswith(".gnn.md"))
    return sorted(sketches)


def require_type_check(returned: object, subject: str) -> None:
    """Fail unless the pinned checker returned its literal success value.

    ``validate_gnn_files`` returns ``True`` when every file validates, ``2``
    when the run completed but files had type/consistency problems **or when no
    GNN files were found**, and ``False`` on a hard failure. Truthiness would
    let ``2`` pass and print ``"verified"``, so only ``is True`` is accepted,
    and the refusal names the value that came back.
    """
    if returned is not True:
        raise SystemExit(f"GNN type checker rejected {subject} (returned {returned!r})")


def verify(pin: dict) -> dict:
    from gnn import __version__
    from gnn.parsers.basic import parse_gnn_formal, validate_gnn_syntax
    from gnn.type_checker import GNNTypeChecker

    expected_version = pin["tag"].removeprefix("v")
    if __version__ != expected_version:
        raise SystemExit(f"installed GNN {__version__!r} does not match {pin['tag']!r}")

    sketches = repository_sketches()
    if sketches:
        for sketch in sketches:
            parsed = parse_gnn_formal(sketch)
            if parsed is None or getattr(parsed, "parse_errors", None):
                raise SystemExit(f"{sketch} did not parse cleanly")
            valid, errors = validate_gnn_syntax(sketch.read_text(encoding="utf-8"))
            if not valid:
                raise SystemExit(f"{sketch} syntax errors: {errors!r}")
        with tempfile.TemporaryDirectory(prefix="repo-gnn-") as output_dir:
            model_dir = Path(output_dir) / "models"
            model_dir.mkdir()
            for index, sketch in enumerate(sketches):
                shutil.copy2(sketch, model_dir / f"{index:03d}_{sketch.name}")
            require_type_check(
                GNNTypeChecker().validate_gnn_files(model_dir, Path(output_dir)),
                "the repository sketches",
            )
        checked = len(sketches)
        source = "repository"
    else:
        exemplar_url = f"https://raw.githubusercontent.com/{pin['repository']}/{pin['revision']}/{EXEMPLAR_RELPATH}"
        with tempfile.TemporaryDirectory(prefix="pinned-exemplar-") as output_dir:
            exemplar = Path(output_dir) / "static_perception.md"
            urllib.request.urlretrieve(exemplar_url, exemplar)
            parsed = parse_gnn_formal(exemplar)
            if parsed is None or getattr(parsed, "parse_errors", None):
                raise SystemExit("pinned exemplar did not parse cleanly")
            valid, errors = validate_gnn_syntax(exemplar.read_text(encoding="utf-8"))
            if not valid:
                raise SystemExit(f"pinned exemplar syntax errors: {errors!r}")
            model_dir = Path(output_dir) / "models"
            model_dir.mkdir()
            shutil.copy2(exemplar, model_dir / exemplar.name)
            require_type_check(
                GNNTypeChecker().validate_gnn_files(model_dir, Path(output_dir)),
                "the pinned exemplar",
            )
        checked = 1
        source = "pinned-exemplar"

    return {
        "gnn-version": __version__,
        "pin-revision": pin["revision"],
        "models": checked,
        "source": source,
        "result": "verified",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pinned GNN conformance check")
    parser.add_argument("--no-install", action="store_true", help="skip installing the pinned parser")
    parser.add_argument("--no-verify", action="store_true", help="only install the pinned parser")
    args = parser.parse_args(argv)
    if args.no_install and args.no_verify:
        parser.error("--no-install and --no-verify together would do nothing")

    pin = load_pin()
    print(
        f"pin: {pin['repository']} {pin['tag']} ({pin['revision']}), schema {pin['schema']}",
        flush=True,
    )
    if not args.no_install:
        print(f"installing: {install(pin)}", flush=True)
    if args.no_verify:
        return 0
    summary = verify(pin)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
