"""The GNN conformance gate must accept only the checker's literal ``True``.

``GNNTypeChecker.validate_gnn_files`` returns ``True`` when every file
validates, ``2`` when the run completed but files had type/consistency
problems (or when no GNN files were found), and ``False`` on a hard failure.
A truthiness test lets ``2`` pass and the gate prints ``"verified"`` anyway, so
these tests pin every non-``True`` outcome to a refusal that names the value.

The wiring tests replace the pinned ``gnn`` package in ``sys.modules``, so they
run offline without the parser install. ``test_pinned_checker_returns_two...``
documents the real contract with the installed parser and skips when it is
absent (CI's ``tests`` job installs only ``requirements-dev.txt``).
"""

import pathlib
import sys
import types

import pytest

import scripts.check_gnn_conformance as gate

PIN = gate.load_pin()
SKETCH_BODY = "## GNNSection\n\nActInfPOMDP\n\n## GNNVersionAndFlags\n\nGNN v1\n"


def _install_fake_gnn(monkeypatch, returned, calls):
    """Make ``verify()``'s deferred ``gnn`` imports resolve to a stub package."""
    stub = types.ModuleType("gnn")
    stub.__version__ = PIN["tag"].removeprefix("v")
    parsers = types.ModuleType("gnn.parsers")
    basic = types.ModuleType("gnn.parsers.basic")
    basic.parse_gnn_formal = lambda path: types.SimpleNamespace(parse_errors=[])
    basic.validate_gnn_syntax = lambda text: (True, [])
    type_checker = types.ModuleType("gnn.type_checker")

    class StubTypeChecker:
        def validate_gnn_files(self, model_dir, output_dir, *args, **kwargs):
            calls.append(
                {
                    "models": sorted(path.name for path in pathlib.Path(model_dir).iterdir()),
                    "output_dir": pathlib.Path(output_dir),
                }
            )
            return returned

    type_checker.GNNTypeChecker = StubTypeChecker
    stub.parsers = parsers
    stub.type_checker = type_checker
    parsers.basic = basic
    for name, module in {
        "gnn": stub,
        "gnn.parsers": parsers,
        "gnn.parsers.basic": basic,
        "gnn.type_checker": type_checker,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def _sketch(tmp_path):
    path = tmp_path / "perception.gnn.md"
    path.write_text(SKETCH_BODY, encoding="utf-8")
    return path


def _stub_exemplar_download(monkeypatch):
    def urlretrieve(url, filename):
        pathlib.Path(filename).write_text(SKETCH_BODY, encoding="utf-8")
        return filename, None

    monkeypatch.setattr(gate.urllib.request, "urlretrieve", urlretrieve)


@pytest.mark.parametrize("returned", [2, False, None, 0])
def test_require_type_check_refuses_every_non_true_outcome(returned):
    with pytest.raises(SystemExit) as excinfo:
        gate.require_type_check(returned, "the repository sketches")
    message = str(excinfo.value)
    assert repr(returned) in message
    assert "the repository sketches" in message


def test_require_type_check_accepts_literal_true():
    assert gate.require_type_check(True, "the repository sketches") is None


@pytest.mark.parametrize("returned", [2, False, None, 0])
def test_verify_refuses_non_true_type_check_for_repository_sketches(monkeypatch, tmp_path, returned):
    calls = []
    _install_fake_gnn(monkeypatch, returned, calls)
    monkeypatch.setattr(gate, "repository_sketches", lambda: [_sketch(tmp_path)])

    with pytest.raises(SystemExit) as excinfo:
        gate.verify(PIN)

    assert repr(returned) in str(excinfo.value)
    assert calls[0]["models"] == ["000_perception.gnn.md"]


def test_verify_reports_verified_when_the_checker_returns_true(monkeypatch, tmp_path):
    calls = []
    _install_fake_gnn(monkeypatch, True, calls)
    monkeypatch.setattr(gate, "repository_sketches", lambda: [_sketch(tmp_path)])

    summary = gate.verify(PIN)

    assert summary["result"] == "verified"
    assert summary["source"] == "repository"
    assert summary["models"] == 1
    assert calls[0]["models"] == ["000_perception.gnn.md"]


@pytest.mark.parametrize("returned", [2, False, None, 0])
def test_verify_refuses_non_true_type_check_for_pinned_exemplar(monkeypatch, tmp_path, returned):
    calls = []
    _install_fake_gnn(monkeypatch, returned, calls)
    monkeypatch.setattr(gate, "repository_sketches", lambda: [])
    _stub_exemplar_download(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        gate.verify(PIN)

    assert repr(returned) in str(excinfo.value)
    assert calls[0]["models"] == ["static_perception.md"]


def test_pinned_checker_returns_two_for_a_type_invalid_sketch(tmp_path):
    """The stub contract above matches the real checker's documented return."""
    pytest.importorskip("gnn")
    from gnn.parsers.basic import validate_gnn_syntax
    from gnn.type_checker import GNNTypeChecker

    text = (
        "## GNNSection\n\nActInfPOMDP\n\n## GNNVersionAndFlags\n\nGNN v1\n\n"
        "## ModelName\n\nType Invalid Fixture\n\n## ModelAnnotation\n\n"
        "A[3,2] with C[2]: the preference length does not match A's observation dimension.\n\n"
        "## StateSpaceBlock\n\nA[3,2,type=float]\nB[2,2,2,type=float]\nC[2,type=float]\n"
        "D[2,1,type=float]\ns[2,1,type=float]\no[3,1,type=int]\nu[1,type=int]\n\n"
        "## Connections\n\nD>s\ns-A\nA-o\ns-B\nB>u\nu>s\n\n"
        "## InitialParameterization\n\nA={\n  (0.9, 0.2),\n  (0.1, 0.8),\n  (0.0, 0.0)\n}\n\n"
        "B={\n  ( (0.95, 0.05), (0.05, 0.95) ),\n  ( (0.05, 0.95), (0.95, 0.05) )\n}\n\n"
        "C={(0.0, 0.0)}\nD={(0.5, 0.5)}\n\n## Time\n\nStatic\n\n"
        "## ActInfOntologyAnnotation\n\nA=LikelihoodMatrix\nB=TransitionMatrix\n"
        "C=PreferenceVector\nD=Prior\ns=HiddenState\no=Observation\nu=Action\n\n"
        "## Footer\n\nType-invalid fixture.\n"
    )
    valid, _ = validate_gnn_syntax(text)
    assert valid is True
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "000_type_invalid.gnn.md").write_text(text, encoding="utf-8")
    returned = GNNTypeChecker().validate_gnn_files(model_dir, tmp_path)
    assert returned == 2
    with pytest.raises(SystemExit) as excinfo:
        gate.require_type_check(returned, "the repository sketches")
    assert "returned 2" in str(excinfo.value)
