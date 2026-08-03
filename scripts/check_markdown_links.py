#!/usr/bin/env python3
"""Check relative markdown links and heading anchors across the repository.

Exits non-zero if any markdown file links to a missing file, or to a heading
anchor that does not exist under GitHub-style slugification. External (http)
links and links inside fenced code blocks are not checked.

Usage: python scripts/check_markdown_links.py
"""

import pathlib
import re
import sys


def slugify(header):
    # GitHub heading anchors: lowercase, strip punctuation, spaces -> hyphens.
    header = header.strip().lower()
    header = re.sub(r"[^\w\s-]", "", header, flags=re.UNICODE)
    return re.sub(r"[\s]+", "-", header)


def lines_outside_fences(path):
    in_fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield lineno, line


def anchors(path):
    result = set()
    for _, line in lines_outside_fences(path):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            result.add(slugify(m.group(2)))
    return result


def iter_links(path):
    for lineno, line in lines_outside_fences(path):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
            yield lineno, target


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    problems = []
    md_files = sorted(root.rglob("*.md"))
    anchors_cache = {}

    for md in md_files:
        rel = md.relative_to(root)
        for lineno, target in iter_links(md):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target.startswith("#"):
                if target[1:] not in anchors(md):
                    problems.append(f"{rel}:{lineno}: broken anchor {target}")
                continue

            frag = ""
            if "#" in target:
                target, frag = target.split("#", 1)
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                problems.append(f"{rel}:{lineno}: missing file {target}")
                continue
            if frag:
                key = resolved.relative_to(root)
                if key not in anchors_cache:
                    anchors_cache[key] = anchors(resolved)
                if frag not in anchors_cache[key]:
                    problems.append(f"{rel}:{lineno}: broken anchor {target}#{frag}")

    for problem in problems:
        print(problem, file=sys.stderr)
    status = "OK" if not problems else f"{len(problems)} problem(s)"
    print(f"checked {len(md_files)} markdown files: {status}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
