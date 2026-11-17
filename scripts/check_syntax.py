#!/usr/bin/env python3
"""Compile authored Python into a temporary cache, never installed environments."""

from __future__ import annotations

import os
import py_compile
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", "build", "dist",
    ".cache", "__pypackages__", "site-packages", "dist-packages",
}


def python_files(root: Path) -> list[Path]:
    files = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        names[:] = sorted(
            name for name in names
            if name not in SKIP_DIRS and not (current / name).is_symlink()
            and not (current / name / "pyvenv.cfg").is_file()
        )
        files.extend(
            current / name for name in filenames
            if name.endswith(".py") and not (current / name).is_symlink()
        )
    return sorted(files)


def main(root: Path = ROOT) -> int:
    errors = []
    with tempfile.TemporaryDirectory(prefix="iris-syntax-") as directory:
        for index, path in enumerate(python_files(root)):
            try:
                py_compile.compile(str(path), cfile=str(Path(directory) / f"{index}.pyc"), doraise=True)
            except py_compile.PyCompileError as exc:
                errors.append(str(exc))
    for error in errors:
        print(error, file=sys.stderr)
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
