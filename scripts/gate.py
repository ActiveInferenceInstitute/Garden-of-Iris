#!/usr/bin/env python3
"""The repository gate: one entry point, one command per arm.

`.github/workflows/ci.yml` calls these arms instead of spelling out commands,
so a local run and a CI run execute the same argv. There is no second copy of
any command.

Usage:
    python scripts/gate.py                  # default arm: fast (offline tests)
    python scripts/gate.py <arm> [<arm>...] # any combination, in the given order
    python scripts/gate.py all              # every distinct check, once each
    python scripts/gate.py list             # table of arms and their commands
    python scripts/gate.py report           # run every arm, refresh
                                            # docs/_generated/GATES.md
    python scripts/gate.py report --check   # fail if the generated facts are stale

Arms:

    syntax  Compile every module. This is the lint arm: the repository has no
            static linter, formatter, or type checker, so there is no `types`
            arm and nothing here to type-check.
    docs    Relative links and heading anchors, then the generated-number
            freshness check.
    fast    The offline unit suite (`-m "not network"`): no key, no network.
    tests   The whole unit suite.
    models  Verify the scripts' model IDs against the live OpenRouter catalog
            (network).
    gnn     Pinned GNN conformance (installs the pinned parser revision).

Every arm exits non-zero on failure. Multiple arms all run; the exit status is
non-zero if any arm failed.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import importlib.metadata
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED_DOC = ROOT / "docs" / "_generated" / "GATES.md"
NETWORK_MARKER = "network"
PYTHON = "python"  # placeholder shown in docs, replaced by sys.executable
MEASUREMENT_HEADING = "## Measured runtimes"
# `report` is the producer of the generated document, so it cannot also require
# that document to be current; it skips exactly this step.
GENERATED_CHECK_STEP = (PYTHON, "scripts/gate.py", "report", "--check")


@dataclasses.dataclass(frozen=True)
class Arm:
    summary: str
    steps: tuple[tuple[str, ...], ...]


ARMS: dict[str, Arm] = {
    "syntax": Arm(
        "Compile every module (`compileall`); the repository's only lint gate.",
        ((PYTHON, "-m", "compileall", "-q", "."),),
    ),
    "docs": Arm(
        "Relative markdown links and heading anchors, then generated-number freshness.",
        ((PYTHON, "scripts/check_markdown_links.py"), GENERATED_CHECK_STEP),
    ),
    "fast": Arm(
        f"Offline unit suite: `pytest tests/ -m \"not {NETWORK_MARKER}\"`.",
        ((PYTHON, "-m", "pytest", "tests", "-q", "-m", f"not {NETWORK_MARKER}"),),
    ),
    "tests": Arm(
        "Whole unit suite: `pytest tests/`.",
        ((PYTHON, "-m", "pytest", "tests", "-q"),),
    ),
    "models": Arm(
        "Model IDs exist in the live OpenRouter catalog (network).",
        ((PYTHON, "scripts/check_openrouter_models.py"),),
    ),
    "gnn": Arm(
        "Pinned GNN conformance: install `.github/gnn-pin.json`'s parser revision, parse and type-check.",
        ((PYTHON, "scripts/check_gnn_conformance.py"),),
    ),
}

# `all` runs each distinct check once: `fast` is omitted because it is the
# offline subset of `tests`, which covers it.
ALL_ARMS = ("syntax", "docs", "tests", "models", "gnn")
# `report` times every arm, including the default `fast` arm that `all` omits.
MEASURED_ARMS = ("syntax", "docs", "fast", "tests", "models", "gnn")
DEFAULT_ARM = "fast"


def expand(step: tuple[str, ...]) -> list[str]:
    return [sys.executable if part == PYTHON else part for part in step]


def display(step: tuple[str, ...]) -> str:
    return " ".join(step)


def run_step(step: tuple[str, ...]) -> int:
    argv = expand(step)
    print(f"$ {display(step)}", flush=True)
    return subprocess.run(argv, cwd=ROOT, stdin=subprocess.DEVNULL).returncode


def run_arm(name: str, generated_check: bool = True) -> tuple[bool, float]:
    arm = ARMS[name]
    print(f"\n== {name}: {arm.summary}", flush=True)
    started = time.monotonic()
    failed = False
    for step in arm.steps:
        if not generated_check and step == GENERATED_CHECK_STEP:
            print(f"$ {display(step)} (skipped: report is producing that document)", flush=True)
            continue
        if run_step(step) != 0:
            failed = True
            break
    elapsed = time.monotonic() - started
    print(f"== {name}: {'FAIL' if failed else 'ok'} ({elapsed:.2f}s)", flush=True)
    return (not failed), elapsed


def collect_tests() -> dict[str, int]:
    """Per-file test counts from pytest collection (a read-only query)."""
    result = subprocess.run(
        expand(ARMS["tests"].steps[0]) + ["--collect-only"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"pytest collection failed:\n{result.stdout}{result.stderr}")
    counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        node_id = line.strip()
        if "::" not in node_id or node_id.startswith("<"):
            continue
        counts[node_id.split("::", 1)[0]] = counts.get(node_id.split("::", 1)[0], 0) + 1
    if not counts:
        raise SystemExit("pytest collection returned no test node IDs")
    return dict(sorted(counts.items()))


def version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "absent"


def render_facts(counts: dict[str, int]) -> str:
    lines = [
        "# Gate arms and checked facts",
        "",
        "<!-- generated by scripts/gate.py report; do not edit by hand -->",
        "",
        "The arms below are the single definition of every check: `.github/workflows/ci.yml`",
        "runs `python scripts/gate.py <arm>`, and a local run executes the same argv.",
        f"Run the default arm with no argument (`{DEFAULT_ARM}`); run every distinct",
        f"check once with `all` (`{' '.join(ALL_ARMS)}`).",
        "",
        "## Arms",
        "",
        "| Arm | Steps | What it checks |",
        "| --- | --- | --- |",
    ]
    for name, arm in ARMS.items():
        steps = "<br>".join(f"`{display(step)}`" for step in arm.steps)
        lines.append(f"| `{name}` | {steps} | {arm.summary} |")
    lines.extend(
        [
            "",
            "`fast` is the offline subset of `tests` (`-m \"not "
            + NETWORK_MARKER
            + "\"`), so `all` runs `tests` and skips `fast`.",
            "",
            "## Test inventory",
            "",
            "| File | Tests |",
            "| --- | --- |",
        ]
    )
    for path, count in counts.items():
        lines.append(f"| `{path}` | {count} |")
    lines.append(f"| **total** | **{sum(counts.values())}** |")
    return "\n".join(lines) + "\n"


def render_measurements(results: list[tuple[str, bool, float]]) -> str:
    recorded = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        MEASUREMENT_HEADING,
        "",
        "One run per arm on the host below, immediately after `python scripts/gate.py report`.",
        "The virtualenv was prepared: `requirements-dev.txt` installed and the `gnn` arm's",
        "pinned parser present from an earlier run, so a `gnn` timing here does not include a",
        "cold clone. These are a record of that run, not a freshness claim and not a CI",
        "claim; re-run `report` to refresh them.",
        "",
        "The table lists every arm, including `fast`, which `all` omits because `tests`",
        "covers it. `report` skips the `docs` arm's freshness step: it is rewriting that",
        "document in this run.",
        "",
        f"- Recorded: {recorded}",
        f"- Host: {platform.platform()} ({platform.machine()})",
        f"- Python: {platform.python_version()}",
        f"- pytest: {version('pytest')}",
        f"- openai: {version('openai')}",
        f"- pandas: {version('pandas')}",
        "",
        "| Arm | Result | Wall time |",
        "| --- | --- | --- |",
    ]
    for name, ok, elapsed in results:
        lines.append(f"| `{name}` | {'ok' if ok else 'FAIL'} | {elapsed:.2f}s |")
    if not results:
        lines.extend(["", "The measurement run did not finish; re-run `python scripts/gate.py report`."])
    return "\n".join(lines) + "\n"


def write_report() -> int:
    facts = render_facts(collect_tests())
    GENERATED_DOC.parent.mkdir(parents=True, exist_ok=True)
    # The facts land first so the documents that link here resolve during this
    # same run; the measurement section is filled in when the arms finish.
    GENERATED_DOC.write_text(facts + "\n" + render_measurements([]), encoding="utf-8")

    results: list[tuple[str, bool, float]] = []
    for name in MEASURED_ARMS:
        ok, elapsed = run_arm(name, generated_check=False)
        results.append((name, ok, elapsed))
    GENERATED_DOC.write_text(facts + "\n" + render_measurements(results), encoding="utf-8")
    print(f"\nreport: wrote {GENERATED_DOC.relative_to(ROOT)}")

    failures = [name for name, ok, _ in results if not ok]
    if failures:
        print(f"report: FAILED arms: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def check_report() -> int:
    facts = render_facts(collect_tests())
    if not GENERATED_DOC.exists():
        print(f"ERROR: {GENERATED_DOC.relative_to(ROOT)} is missing; run `python scripts/gate.py report`", file=sys.stderr)
        return 1
    committed = GENERATED_DOC.read_text(encoding="utf-8")
    if MEASUREMENT_HEADING not in committed:
        print(f"ERROR: {GENERATED_DOC.relative_to(ROOT)} has no `{MEASUREMENT_HEADING}` section", file=sys.stderr)
        return 1
    if committed.split(MEASUREMENT_HEADING, 1)[0].rstrip("\n") + "\n" != facts:
        print(
            f"ERROR: the generated facts in {GENERATED_DOC.relative_to(ROOT)} are stale; "
            "run `python scripts/gate.py report`",
            file=sys.stderr,
        )
        return 1
    print(f"{GENERATED_DOC.relative_to(ROOT)}: arms and test inventory match the code")
    return 0


def list_arms() -> int:
    for name, arm in ARMS.items():
        print(f"{name:8s} {arm.summary}")
        for step in arm.steps:
            print(f"         $ {display(step)}")
    print(f"\ndefault arm: {DEFAULT_ARM}")
    print(f"all:          {' '.join(ALL_ARMS)}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="gate.py", description=__doc__.splitlines()[0])
    parser.add_argument("arms", nargs="*", help=f"{', '.join(ARMS)}, all (default: {DEFAULT_ARM})")
    parser.add_argument("--check", action="store_true", help="with `report`: verify the generated facts are current")
    args = parser.parse_args(argv)

    if not args.arms:
        if args.check:
            parser.error("--check is only valid with `report`")
        args.arms = [DEFAULT_ARM]

    names: list[str] = []
    for name in args.arms:
        if name == "report":
            return check_report() if args.check else write_report()
        if name == "list":
            return list_arms()
        if name == "all":
            names.extend(ALL_ARMS)
            continue
        if name not in ARMS:
            parser.error(f"unknown arm {name!r}; choose from {', '.join(ARMS)}, all, list, or report")
        names.append(name)

    if args.check:
        parser.error("--check is only valid with `report`")

    failures = [name for name in names if not run_arm(name)[0]]
    if failures:
        print(f"\nFAILED arms: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
