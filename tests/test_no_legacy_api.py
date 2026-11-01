"""Guard the current-API migration: no legacy shim or pre-1.0 call style."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

LEGACY_PATTERNS = [
    r"openai_legacy",
    r"openai\.Completion\.create",
    r"openai\.ChatCompletion\.create",
    r"openai\.error\.",
    r"openai\.api_key\s*=",
]


def _python_files():
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        if path.name == "test_no_legacy_api.py":  # this file names the patterns
            continue
        yield path


def test_no_python_file_uses_the_legacy_surface():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for pattern in LEGACY_PATTERNS:
            if re.search(pattern, text):
                offenders.append(f"{path.relative_to(ROOT)}: {pattern}")
    assert offenders == []


def test_shim_file_is_gone():
    assert not (ROOT / "openai_legacy.py").exists()
