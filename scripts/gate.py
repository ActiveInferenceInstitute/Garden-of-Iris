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
    python scripts/gate.py measure --label before|after
                                            # one run per arm, write a timing
                                            # receipt under docs/_generated/
    python scripts/gate.py report           # render docs/_generated/GATES.md
                                            # from the code and those receipts
    python scripts/gate.py report --check   # fail if the generated facts are
                                            # stale, or the receipts drifted

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

Refresh order for the generated document: `report` (facts), then
`measure --label after` (the `docs` arm's freshness check needs the facts to be
current), then `report` again to render the comparison. `measure --label before`
records the pre-gate baseline and only needs re-running if that baseline changes.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = ROOT / "docs" / "_generated"
GENERATED_DOC = GENERATED_DIR / "GATES.md"
RECEIPT_SCHEMA = "gate-receipt/v1"
RECEIPTS = {
    "before": GENERATED_DIR / "gate-before.json",
    "after": GENERATED_DIR / "gate-after.json",
}
NETWORK_MARKER = "network"
PYTHON = "python"  # placeholder shown in docs, replaced by sys.executable
MEASUREMENT_HEADING = "## Measured runtimes"
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

# The pre-gate commands, as `.github/workflows/ci.yml` ran them at a2ad766.
# `fast` did not exist; `docs` was the link check alone. The `gnn` pair
# reproduces that job's two workflow steps — install the pinned parser, then
# verify it — against the implementation extracted from those heredocs, so the
# comparison measures the wrapper change, not different parsing work.
BASELINE_ARMS: dict[str, Arm] = {
    "syntax": Arm(
        "Compile every module.",
        ((PYTHON, "-m", "compileall", "-q", "."),),
    ),
    "docs": Arm(
        "Relative markdown links and heading anchors.",
        ((PYTHON, "scripts/check_markdown_links.py"),),
    ),
    "tests": Arm(
        "Whole unit suite.",
        ((PYTHON, "-m", "pytest", "tests", "-q"),),
    ),
    "models": Arm(
        "Model IDs exist in the live OpenRouter catalog (network).",
        ((PYTHON, "scripts/check_openrouter_models.py"),),
    ),
    "gnn": Arm(
        "Install the pinned parser (workflow step 1), then verify it (step 2).",
        (
            (PYTHON, "scripts/check_gnn_conformance.py", "--no-verify"),
            (PYTHON, "scripts/check_gnn_conformance.py", "--no-install"),
        ),
    ),
}

# `all` runs each distinct check once: `fast` is omitted because it is the
# offline subset of `tests`, which covers it.
ALL_ARMS = ("syntax", "docs", "tests", "models", "gnn")
# `measure` times every arm, including the default `fast` arm that `all` omits.
MEASURED_ARMS = ("syntax", "docs", "fast", "tests", "models", "gnn")
BASELINE_ORDER = tuple(BASELINE_ARMS)
DEFAULT_ARM = "fast"


def expand(step: tuple[str, ...]) -> list[str]:
    return [sys.executable if part == PYTHON else part for part in step]


def display(step: tuple[str, ...]) -> str:
    return " ".join(step)


def run_step(step: tuple[str, ...]) -> int:
    argv = expand(step)
    print(f"$ {display(step)}", flush=True)
    return subprocess.run(argv, cwd=ROOT, stdin=subprocess.DEVNULL).returncode


def run_arm(name: str, arms: dict[str, Arm]) -> tuple[bool, float]:
    arm = arms[name]
    print(f"\n== {name}: {arm.summary}", flush=True)
    started = time.monotonic()
    failed = False
    for step in arm.steps:
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


def receipt_body(label: str, arms: dict[str, Arm], order: tuple[str, ...]) -> dict:
    results = []
    for name in order:
        ok, elapsed = run_arm(name, arms)
        results.append(
            {
                "arm": name,
                "commands": [display(step) for step in arms[name].steps],
                "wall_s": round(elapsed, 3),
                "ok": ok,
            }
        )
    return {
        "schema": RECEIPT_SCHEMA,
        "label": label,
        "recorded": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {
            "host": f"{platform.platform()} ({platform.machine()})",
            "python": platform.python_version(),
            "versions": {name: version(name) for name in ("pytest", "openai", "pandas")},
        },
        "arms": results,
    }


def measure(label: str, out: str | None) -> int:
    arms, order = (
        (BASELINE_ARMS, BASELINE_ORDER) if label == "before" else (ARMS, MEASURED_ARMS)
    )
    receipt = receipt_body(label, arms, order)
    path = Path(out) if out else RECEIPTS[label]
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    failures = [row["arm"] for row in receipt["arms"] if not row["ok"]]
    print(f"\nmeasure: wrote {path} ({label} run, one pass per arm)")
    if failures:
        print(f"measure: FAILED arms: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def load_receipt(label: str) -> dict | None:
    path = RECEIPTS[label]
    if not path.exists():
        return None
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("label") != label:
        raise SystemExit(f"{path}: expected schema {RECEIPT_SCHEMA!r} and label {label!r}")
    return receipt


def receipt_drift(label: str, receipt: dict, arms: dict[str, Arm], order: tuple[str, ...]) -> str | None:
    """Name the first difference between a receipt and the code, or None."""
    recorded = [row.get("arm") for row in receipt.get("arms", [])]
    if recorded != list(order):
        return f"{label} receipt covers {recorded}, the code defines {list(order)}"
    for row in receipt["arms"]:
        expected = [display(step) for step in arms[row["arm"]].steps]
        if row.get("commands") != expected:
            return f"{label} receipt recorded {row['arm']} as {row.get('commands')}, the code runs {expected}"
        if not isinstance(row.get("wall_s"), (int, float)):
            return f"{label} receipt has no wall time for {row['arm']}"
    return None


def render_measurements(before: dict | None, after: dict | None) -> str:
    lines = [
        MEASUREMENT_HEADING,
        "",
        "Two committed receipts: `docs/_generated/gate-before.json` is the pre-gate",
        "baseline (`measure --label before`: the commands `.github/workflows/ci.yml` ran at",
        "a2ad766) and `docs/_generated/gate-after.json` is the gate arms (`measure --label",
        "after`).",
        "Each receipt is one pass per arm and covers every command that side ran: the",
        "baseline `docs` entry is the link check alone, while the gate `docs` arm also runs",
        "the generated-facts check. `report` renders the receipts; it times nothing itself.",
        "",
        "These are measurements on one host in one prepared virtualenv, not a CI claim and",
        "not a freshness claim. Re-measure after changing an arm, then re-run `report`.",
        "",
    ]
    if before is None or after is None:
        lines.append("A receipt is missing, so there is no comparison yet: run")
        lines.append("`python scripts/gate.py measure --label before` (and `after`), then `report`.")
        return "\n".join(lines) + "\n"

    environment = after["environment"]
    lines.extend(
        [
            f"- Before receipt: {before['recorded']}",
            f"- After receipt: {after['recorded']}",
            f"- Host: {environment['host']}",
            f"- Python: {environment['python']}",
            "- Versions: "
            + ", ".join(f"{name} {value}" for name, value in environment["versions"].items()),
            "",
            "| Arm | Before | After | Δ |",
            "| --- | --- | --- | --- |",
        ]
    )
    before_by_arm = {row["arm"]: row for row in before["arms"]}
    for row in after["arms"]:
        name = row["arm"]
        earlier = before_by_arm.get(name)
        if earlier is None:
            before_text, delta = "— (arm did not exist)", "—"
        elif earlier["commands"] == row["commands"]:
            before_text, delta = f"{earlier['wall_s']:.2f}s", "same command: variance"
        else:
            before_text = f"{earlier['wall_s']:.2f}s"
            delta = f"{row['wall_s'] - earlier['wall_s']:+.2f}s"
        result = "" if row["ok"] else " (FAIL)"
        lines.append(f"| `{name}` | {before_text} | {row['wall_s']:.2f}s{result} | {delta} |")

    lines.extend(
        [
            "",
            "Δ appears only where the command changed. Where both sides ran the identical",
            "command the column says `same command: variance`, because one pass per side cannot",
            "separate a real difference from warm-cache noise. `docs` gained the generated-facts",
            "check and `gnn` collapsed two workflow steps into one arm; those Δ values describe",
            "changed work, not a speed change. No speedup is claimed.",
            "",
            "### Baseline commands",
            "",
            "| Arm | Commands as recorded |",
            "| --- | --- |",
        ]
    )
    for row in before["arms"]:
        commands = "<br>".join(f"`{command}`" for command in row["commands"])
        lines.append(f"| `{row['arm']}` | {commands} |")
    return "\n".join(lines) + "\n"


def write_report() -> int:
    before = load_receipt("before")
    after = load_receipt("after")
    for label, receipt, arms, order in (
        ("before", before, BASELINE_ARMS, BASELINE_ORDER),
        ("after", after, ARMS, MEASURED_ARMS),
    ):
        if receipt is None:
            continue
        problem = receipt_drift(label, receipt, arms, order)
        if problem:
            print(f"report: {problem}; re-run `measure --label {label}`", file=sys.stderr)
            return 1
    facts = render_facts(collect_tests())
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DOC.write_text(facts + "\n" + render_measurements(before, after), encoding="utf-8")
    print(f"report: wrote {GENERATED_DOC.relative_to(ROOT)}")
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
    for label, arms, order in (("before", BASELINE_ARMS, BASELINE_ORDER), ("after", ARMS, MEASURED_ARMS)):
        receipt = load_receipt(label)
        if receipt is None:
            continue
        problem = receipt_drift(label, receipt, arms, order)
        if problem:
            print(f"ERROR: {problem}; run `python scripts/gate.py measure --label {label}`", file=sys.stderr)
            return 1
    print(f"{GENERATED_DOC.relative_to(ROOT)}: arms, test inventory, and receipts match the code")
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
    parser.add_argument("arms", nargs="*", help=f"{', '.join(ARMS)}, all, list, measure, report (default: {DEFAULT_ARM})")
    parser.add_argument("--check", action="store_true", help="with `report`: verify the generated facts and receipts")
    parser.add_argument("--label", choices=tuple(RECEIPTS), help="with `measure`: which side to time")
    parser.add_argument("--out", help="with `measure`: receipt path (default: docs/_generated/gate-<label>.json)")
    args = parser.parse_args(argv)

    if "measure" in args.arms:
        if args.arms != ["measure"]:
            parser.error("`measure` runs alone")
        if args.label is None:
            parser.error("`measure` needs --label before|after")
        if args.check:
            parser.error("--check is only valid with `report`")
        return measure(args.label, args.out)
    if args.label or args.out:
        parser.error("--label and --out are only valid with `measure`")

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

    failures = [name for name in names if not run_arm(name, ARMS)[0]]
    if failures:
        print(f"\nFAILED arms: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
