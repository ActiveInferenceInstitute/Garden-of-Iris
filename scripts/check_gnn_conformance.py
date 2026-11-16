#!/usr/bin/env python3
"""Exact-pin GNN conformance with independently reviewed pre-import admission.

GNN_BOOTSTRAP and GNN_SOURCE_MANIFEST select the reviewed, digest-bound files;
neither is discovered inside the parser installation. Installed mode requires
the real distribution's matching PEP 610 Git origin and complete source content.
Explicit source mode additionally requires GNN_PACKAGE_ROOT (the gnn package
directory), GNN_ORIGIN_MODE=source and --no-install (or GNN_NO_INSTALL=1).
No failed installed admission falls back to a checkout or another interpreter.

The gate and CI call this entry point. All parser, syntax and type-checker work
runs inside the producer's qualified_source lifetime, with one in-process file
worker. With no repository sketches, the default still downloads the pinned
upstream exemplar; --exemplar / GNN_EXEMPLAR explicitly selects a local fixture.
--no-install alone is therefore not an offline command. --no-verify installs
only and cannot claim source qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
PIN_PATH = ROOT / ".github" / "gnn-pin.json"
PIN_COMMIT = "8f293d9ba810e6eda5c09842d9c7ed9ffa5f92c1"
PIN_TAG = "v5.0.3"
BOOTSTRAP_SHA256 = "f638d4c01fe7de31e43d793e59bf382d0c3d1a82f365c59238334a2b40adfb37"
MANIFEST_SHA256 = "17a35bb2114e76a38119128d290d12377cb641652d70788000482366dca0a14a"
RUNTIME_DEPENDENCIES = ("defusedxml", "psutil", "pyyaml")
EXEMPLAR_RELPATH = "input/gnn_files/basics/static_perception.md"

class ConformanceError(ValueError):
    """A failed admission or parser verdict; never a fallback instruction."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _checked_resource(path: Path | None, digest: str, label: str) -> bytes:
    if path is None:
        raise ConformanceError(f"{label}-unavailable", f"select the reviewed {label} file explicitly")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ConformanceError(f"{label}-unavailable", f"cannot read {label}: {exc}") from exc
    if hashlib.sha256(content).hexdigest() != digest:
        raise ConformanceError(f"{label}-hash-mismatch", f"{label} differs from the independently frozen SHA-256")
    return content


def _load_bootstrap(path: Path | None) -> ModuleType:
    if any(name == "gnn" or name.startswith("gnn.") for name in sys.modules):
        raise ConformanceError("source-already-imported", "GNN admission requires a fresh process")
    content = _checked_resource(path, BOOTSTRAP_SHA256, "bootstrap")
    # Dataclasses require a registered module. Never import through gnn, reread
    # the executable file, or use a loader that could select cached bytecode.
    name = "_iris_reviewed_gnn_bootstrap"
    module = ModuleType(name)
    module.__file__ = str(path.resolve())
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(content, module.__file__, "exec", dont_inherit=True), module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module


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


def install(pin) -> str:
    pip_install(*RUNTIME_DEPENDENCIES)
    spec = f"generalized-notation-notation @ git+https://github.com/{pin.repository}.git@{pin.commit}"
    pip_install("--no-deps", spec)
    return spec




def verify(
    *,
    bootstrap_path: Path | None,
    manifest_path: Path | None,
    origin_mode: str = "installed",
    package_root: Path | None = None,
    exemplar: Path | None = None,
    install_parser: bool = False,
    install_only: bool = False,
) -> dict:
    if not (3, 11) <= sys.version_info[:2] < (3, 15):
        raise ConformanceError(
            "runtime-unsupported",
            "the pinned GNN parser requires Python >=3.11,<3.15; select a compatible interpreter explicitly",
        )
    if origin_mode not in {"installed", "source"}:
        raise ConformanceError("source-origin-invalid", "origin mode must be installed or source")
    if origin_mode == "source" and (package_root is None or install_parser):
        raise ConformanceError(
            "source-root-invalid", "source mode requires an explicit package root and --no-install"
        )
    if install_only and not install_parser:
        raise ConformanceError("invocation-invalid", "install-only mode must install the parser")

    bootstrap = _load_bootstrap(bootstrap_path)
    manifest = _checked_resource(manifest_path, MANIFEST_SHA256, "source-manifest")
    pin = bootstrap.read_pin(PIN_PATH)
    if (
        pin.schema != bootstrap.PIN_SCHEMA
        or pin.repository != bootstrap.UPSTREAM_REPOSITORY
        or pin.commit != PIN_COMMIT
        or pin.tag != PIN_TAG
    ):
        raise ConformanceError("source-pin-mismatch", "the reviewed resources bind exactly Garden's v5.0.3 pin")
    print(f"pin: {pin.repository} {pin.tag} ({pin.commit}), schema {pin.schema}", flush=True)
    if install_parser:
        print(f"installing: {install(pin)}", flush=True)
    if install_only:
        return {"pin-revision": pin.commit, "result": "installed", "source-qualified": False}

    original_path = sys.path[:]
    try:
        if origin_mode == "source":
            # Deliberate selection only. Installed mode never injects a checkout
            # into resolution, including after a missing/invalid PEP 610 record.
            package_root = package_root.expanduser().resolve()
            sys.path.insert(0, str(package_root.parent))
        with bootstrap.qualified_source(
            pin,
            manifest=manifest,
            manifest_sha256=MANIFEST_SHA256,
            package_root=package_root,
            origin_mode=origin_mode,
        ) as qualification:
            from gnn import __version__
            from gnn.parsers.basic import parse_gnn_formal, validate_gnn_syntax
            from gnn.type_checker import GNNTypeChecker

            if __version__ != pin.tag.removeprefix("v"):
                raise ConformanceError("source-version-mismatch", "GNN version differs from the pinned release")
            sketches = bootstrap.discover_specs(ROOT, pin)
            source = "repository" if sketches else "pinned-exemplar"
            with tempfile.TemporaryDirectory(prefix="iris-gnn-") as output_dir:
                output = Path(output_dir)
                if not sketches:
                    if exemplar is None:
                        exemplar = output / "static_perception.md"
                        url = f"https://raw.githubusercontent.com/{pin.repository}/{pin.commit}/{EXEMPLAR_RELPATH}"
                        urllib.request.urlretrieve(url, exemplar)
                    else:
                        source = "local-exemplar"
                    sketches = [exemplar]
                model_dir = output / "models"
                model_dir.mkdir()
                for index, sketch in enumerate(sketches):
                    parsed = parse_gnn_formal(sketch)
                    if parsed is None or getattr(parsed, "parse_errors", None):
                        raise ConformanceError("parser-rejected", f"{sketch} did not parse cleanly")
                    valid, errors = validate_gnn_syntax(sketch)
                    if not valid:
                        raise ConformanceError("syntax-rejected", f"{sketch} syntax errors: {errors!r}")
                    shutil.copy2(sketch, model_dir / f"{index:03d}.gnn.md")
                # The producer's one-worker path executes in this process.
                # A spawned checker would need its own pre-import admission.
                type_result = GNNTypeChecker().validate_gnn_files(model_dir, output, file_workers=1)
                if not type_result:
                    raise ConformanceError("type-check-rejected", "GNN type checker rejected the selected models")
        # The context has revalidated every loaded member and the full inventory.
        # Also bind the independent input files through completion, not just entry.
        _checked_resource(bootstrap_path, BOOTSTRAP_SHA256, "bootstrap")
        _checked_resource(manifest_path, MANIFEST_SHA256, "source-manifest")
    finally:
        sys.path[:] = original_path

    return {
        "gnn-version": __version__,
        "pin-revision": pin.commit,
        "models": len(sketches),
        "source": source,
        "result": "verified",
        "type-check-result": type_result,
        "source-qualification": qualification,
        "runtime": {"executable": sys.executable, "version": sys.version.split()[0]},
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Exact-pin, source-qualified GNN conformance")
    no_install = os.environ.get("GNN_NO_INSTALL", "0")
    if no_install not in {"0", "1"}:
        parser.error("GNN_NO_INSTALL must be 0 or 1")
    parser.add_argument("--no-install", action="store_true", default=no_install == "1",
                        help="skip installing the pinned parser (GNN_NO_INSTALL=1)")
    parser.add_argument("--no-verify", action="store_true", help="only install; never claim qualification")
    parser.add_argument("--bootstrap", type=Path, default=os.environ.get("GNN_BOOTSTRAP"),
                        help="independently reviewed bootstrap file (GNN_BOOTSTRAP)")
    parser.add_argument("--source-manifest", type=Path, default=os.environ.get("GNN_SOURCE_MANIFEST"),
                        help="independent complete v5.0.3 source manifest (GNN_SOURCE_MANIFEST)")
    parser.add_argument("--origin-mode", choices=("installed", "source"),
                        default=os.environ.get("GNN_ORIGIN_MODE", "installed"))
    parser.add_argument("--package-root", type=Path, default=os.environ.get("GNN_PACKAGE_ROOT"),
                        help="expected gnn package directory; mandatory in source mode")
    parser.add_argument("--exemplar", type=Path, default=os.environ.get("GNN_EXEMPLAR"),
                        help="explicit local fallback fixture; otherwise fetch the pinned exemplar")
    args = parser.parse_args(argv)
    if args.no_install and args.no_verify:
        parser.error("--no-install and --no-verify together would do nothing")
    try:
        summary = verify(
            bootstrap_path=args.bootstrap,
            manifest_path=args.source_manifest,
            origin_mode=args.origin_mode,
            package_root=args.package_root,
            exemplar=args.exemplar,
            install_parser=not args.no_install,
            install_only=args.no_verify,
        )
    except (ConformanceError, OSError, ValueError) as exc:
        print(json.dumps({
            "result": "failed",
            "code": getattr(exc, "code", "conformance-failed"),
            "error": str(exc),
        }, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
