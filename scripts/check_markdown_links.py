#!/usr/bin/env python3
"""Member adapter for the digest-pinned Publishing documentation checks.

The gate retains its existing command; link and index rules come from the lead.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "gate"))

import arm_docs
import identity
import identity_selftest

# Preserve the member's scope, including new, untracked documentation. Do not
# traverse installed dependency documentation or tooling caches.
SKIP_DIRS = {
    ".git", ".mypy_cache", ".pytest_cache", ".tox", ".venv",
    ".ipynb_checkpoints", "node_modules", "venv", "env", "__pycache__",
}


def markdown_files():
    return sorted(
        path for path in ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts[:-1])
    )


def main():
    contract = ROOT / "docs" / "workflows" / "publishing.md"
    if identity.main([]):
        return 1
    for name in identity.recorded_digests(contract):
        artifact = identity.resolve_artifact(ROOT, name)
        if artifact is None:
            print(f"publishing: cannot resolve {name}", file=sys.stderr)
            return 1
        if identity.main(["--verify-copy", str(artifact.relative_to(ROOT))]):
            return 1
    problems = identity_selftest.run()
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print("identity selftest: matching Python copy passes; drifted copy fails")

    arm_docs.tracked_markdown = markdown_files
    arm_docs.check_links()
    arm_docs.check_docs_index()
    for problem in arm_docs.failures:
        print(f"docs: FAIL {problem}", file=sys.stderr)
    print(f"checked {len(markdown_files())} markdown files: "
          f"{'FAIL' if arm_docs.failures else 'OK'} (canonical links and index coverage)")
    return 1 if arm_docs.failures else 0


if __name__ == "__main__":
    sys.exit(main())
