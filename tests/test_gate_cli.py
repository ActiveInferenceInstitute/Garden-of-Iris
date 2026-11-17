"""Offline CLI and authored-tree regressions; no real gate arm is launched."""

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(monkeypatch, filename):
    name = "iris_test_" + Path(filename).stem
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("arguments", [
    ["fast", "report"], ["list", "fast"], ["report", "all"],
    ["all", "list"], ["list", "--check"], ["fast", "unknown"],
    ["measure", "fast", "--label", "after"], ["fast", "--check"],
])
def test_invalid_cli_rejects_before_any_arm_or_generated_write(monkeypatch, arguments):
    gate = _load(monkeypatch, "gate.py")

    def forbidden(*args, **kwargs):
        pytest.fail("invalid CLI reached execution or report writing")

    for name in ("run_arm", "write_report", "check_report", "list_arms", "measure"):
        monkeypatch.setattr(gate, name, forbidden)
    with pytest.raises(SystemExit) as error:
        gate.main(arguments)
    assert error.value.code == 2


def test_valid_multi_arm_request_preserves_order_and_reports_failure(monkeypatch):
    gate = _load(monkeypatch, "gate.py")
    calls = []

    def run(name, arms):
        calls.append(name)
        return name != "syntax", []

    monkeypatch.setattr(gate, "run_arm", run)
    assert gate.main(["syntax", "tests"]) == 1
    assert calls == ["syntax", "tests"]


def test_authored_syntax_excludes_environment_and_symlink_contents(tmp_path, monkeypatch, capsys):
    syntax = _load(monkeypatch, "check_syntax.py")
    root = tmp_path / "project"
    root.mkdir()
    (root / "authored.py").write_text("answer = 42\n", encoding="utf-8")
    for directory in (".venv", "node_modules", ".git", ".cache"):
        location = root / directory
        location.mkdir()
        (location / "dependency.py").write_text("def broken(\n", encoding="utf-8")
    environment = root / "custom-runtime"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("home = synthetic\n", encoding="utf-8")
    (environment / "dependency.py").write_text("def broken(\n", encoding="utf-8")
    external = tmp_path / "external"
    external.mkdir()
    (external / "linked.py").write_text("def broken(\n", encoding="utf-8")
    (root / "linked-directory").symlink_to(external, target_is_directory=True)
    (root / "linked.py").symlink_to(external / "linked.py")
    assert syntax.main(root) == 0
    hidden = root / ".authored"
    hidden.mkdir()
    (hidden / "invalid.py").write_text("def hidden_invalid(\n", encoding="utf-8")
    (root / "invalid.py").write_text("def authored_invalid(\n", encoding="utf-8")
    assert syntax.main(root) == 1
    error = capsys.readouterr().err
    assert str(hidden / "invalid.py") in error
    assert str(root / "invalid.py") in error
    assert "dependency.py" not in error
    assert not list(root.rglob("*.pyc"))
    assert not list(root.rglob("__pycache__"))


@pytest.mark.parametrize("option, expected", [([], 0), (["--gnn-admission"], 28)])
def test_reviewed_input_gnn_tests_are_selected_only_by_the_admission_option(option, expected):
    import os
    import subprocess

    environment = {key: value for key, value in os.environ.items() if not key.startswith("GNN_")}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_gnn_conformance.py", "--collect-only", "-q",
         "-p", "no:cacheprovider", *option],
        cwd=ROOT, env=environment, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120,
    )
    selected = [line for line in result.stdout.splitlines() if line.startswith("tests/test_gnn_conformance.py::")]
    assert len(selected) == expected, result.stdout + result.stderr
    if not option:
        assert "28 deselected" in result.stdout
