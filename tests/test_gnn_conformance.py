"""Real-file/process GNN admission controls; no installs, network or fake parsers.

The parent supplies GNN_BOOTSTRAP, GNN_SOURCE_MANIFEST, GNN_PACKAGE_ROOT and
GNN_EXEMPLAR from its independently reviewed v5.0.3 delivery. The module is
selected only by `--gnn-admission` (the `admission` gate arm); there, missing
inputs are failed prerequisites, not skips or installed-mode qualification. All mutable
copies and process output belong to pytest's disposable temporary root.
"""

import importlib.util
import json
import os
import py_compile
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.gnn_resources

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_NAMES = (
    "GNN_BOOTSTRAP", "GNN_SOURCE_MANIFEST", "GNN_PACKAGE_ROOT", "GNN_EXEMPLAR",
)
DRIVER = """
import runpy
import sys
from pathlib import Path
project = Path(sys.argv[1])
entry = sys.argv[2]
sys.argv = [str(project / 'scripts' / entry), *sys.argv[3:]]
{prelude}
runpy.run_path(sys.argv[0], run_name='__main__')
"""


@pytest.fixture(scope="module")
def inputs():
    missing = [name for name in RESOURCE_NAMES if not os.environ.get(name)]
    if missing:
        pytest.fail("parent must bind the real reviewed GNN inputs: " + ", ".join(missing))
    paths = {name: Path(os.environ[name]).expanduser().resolve() for name in RESOURCE_NAMES}
    for name, path in paths.items():
        if not path.exists():
            pytest.fail(f"{name} is unavailable: {path}")
    return paths


@pytest.fixture
def project(tmp_path, inputs):
    root = tmp_path / "consumer"
    (root / "scripts").mkdir(parents=True)
    (root / ".github").mkdir()
    for name in ("check_gnn_conformance.py", "gate.py"):
        shutil.copyfile(ROOT / "scripts" / name, root / "scripts" / name)
    shutil.copyfile(ROOT / ".github" / "gnn-pin.json", root / ".github" / "gnn-pin.json")
    resources = tmp_path / "reviewed"
    resources.mkdir()
    environment = os.environ.copy()
    for name in (*RESOURCE_NAMES, "GNN_NO_INSTALL", "GNN_ORIGIN_MODE", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    for name in ("GNN_BOOTSTRAP", "GNN_SOURCE_MANIFEST", "GNN_EXEMPLAR"):
        target = resources / inputs[name].name
        shutil.copyfile(inputs[name], target)
        environment[name] = str(target)
    temporary = tmp_path / "runtime"
    temporary.mkdir()
    environment.update(
        GNN_PACKAGE_ROOT=str(inputs["GNN_PACKAGE_ROOT"]),
        GNN_ORIGIN_MODE="source",
        GNN_NO_INSTALL="1",
        PYTHONDONTWRITEBYTECODE="1",
        TMPDIR=str(temporary),
        MPLCONFIGDIR=str(temporary / "matplotlib"),
        XDG_CACHE_HOME=str(temporary / "cache"),
    )
    return root, environment


def _run(project, *, entry="check_gnn_conformance.py", arguments=(), prelude="", python=None):
    root, environment = project
    return subprocess.run(
        [python or sys.executable, "-I", "-B", "-c", DRIVER.format(prelude=textwrap.dedent(prelude)),
         str(root), entry, *arguments],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _reports(output):
    reports = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and "result" in value:
            reports.append(value)
    return reports


def _success(completed):
    assert completed.returncode == 0, completed.stdout + completed.stderr
    reports = _reports(completed.stdout)
    assert len(reports) == 1, completed.stdout
    report = reports[0]
    assert report["result"] == "verified"
    assert report["type-check-result"] is True
    qualification = report["source-qualification"]
    assert qualification["ok"] is True
    assert qualification["status"] == "qualified"
    assert qualification["preimport"] is True
    assert qualification["imports_verified"] is True
    assert qualification["origin"]["kind"] == "explicit-source"
    assert qualification["origin"]["vcs_verified"] is False
    assert qualification["execution_verified"] is False
    assert {"gnn", "gnn.parsers.basic", "gnn.type_checker.checking.core"} <= set(qualification["loaded_modules"])
    return report


def _failure(completed, *codes):
    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert not any(report["result"] == "verified" for report in _reports(completed.stdout))
    reports = _reports(completed.stderr)
    assert len(reports) == 1, completed.stdout + completed.stderr
    assert reports[0]["result"] == "failed"
    assert reports[0]["code"] in codes, reports[0]


def _mutable_package(project, tmp_path, inputs):
    package = tmp_path / "selected" / "gnn"
    shutil.copytree(
        inputs["GNN_PACKAGE_ROOT"], package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    project[1]["GNN_PACKAGE_ROOT"] = str(package)
    return package


def test_direct_local_exemplar_executes_real_verdict_under_full_manifest(project):
    report = _success(_run(project))
    manifest = json.loads(Path(project[1]["GNN_SOURCE_MANIFEST"]).read_text(encoding="utf-8"))
    assert report["source"] == "local-exemplar"
    assert report["models"] == 1
    assert report["source-qualification"]["file_count"] == len(manifest["files"])
    assert report["source-qualification"]["commit"] == manifest["commit"]
    package = Path(project[1]["GNN_PACKAGE_ROOT"])
    assert report["source-qualification"]["loaded_modules"]["gnn.parsers.basic"]["path"] == str(package / "parsers" / "basic.py")


def test_repository_models_use_the_same_guarded_parser_and_checker(project):
    root, environment = project
    models = root / "models"
    models.mkdir()
    for name in ("first.gnn.md", "second.gnn.md"):
        shutil.copyfile(environment["GNN_EXEMPLAR"], models / name)
    environment.pop("GNN_EXEMPLAR")
    report = _success(_run(project))
    assert report["source"] == "repository"
    assert report["models"] == 2


@pytest.mark.parametrize("repository_model", [False, True])
def test_real_type_invalid_model_cannot_publish_a_verified_verdict(project, repository_model):
    root, environment = project
    target = root / "invalid.gnn.md" if repository_model else Path(environment["GNN_EXEMPLAR"])
    target.write_text(
        "## GNNSection\n\nActInfPOMDP\n\n## GNNVersionAndFlags\n\nGNN v1\n\n"
        "## ModelName\n\nType Invalid Fixture\n\n## ModelAnnotation\n\n"
        "A[3,2] with C[2]: preference length differs from the observation dimension.\n\n"
        "## StateSpaceBlock\n\nA[3,2,type=float]\nB[2,2,2,type=float]\nC[2,type=float]\n"
        "D[2,1,type=float]\ns[2,1,type=float]\no[3,1,type=int]\nu[1,type=int]\n\n"
        "## Connections\n\nD>s\ns-A\nA-o\ns-B\nB>u\nu>s\n\n"
        "## InitialParameterization\n\nA={\n  (0.9, 0.2),\n  (0.1, 0.8),\n  (0.0, 0.0)\n}\n\n"
        "B={\n  ( (0.95, 0.05), (0.05, 0.95) ),\n  ( (0.05, 0.95), (0.95, 0.05) )\n}\n\n"
        "C={(0.0, 0.0)}\nD={(0.5, 0.5)}\n\n## Time\n\nStatic\n\n"
        "## ActInfOntologyAnnotation\n\nA=LikelihoodMatrix\nB=TransitionMatrix\n"
        "C=PreferenceVector\nD=Prior\ns=HiddenState\no=Observation\nu=Action\n\n"
        "## Footer\n\nType-invalid regression fixture.\n",
        encoding="utf-8",
    )
    completed = _run(project)
    _failure(completed, "type-check-rejected")
    assert "returned 2" in completed.stderr


def test_gate_uses_the_selected_real_interpreter_for_the_entire_verdict(project):
    report = _success(_run(project, entry="gate.py", arguments=("gnn",)))
    assert Path(report["runtime"]["executable"]) == Path(sys.executable)


def test_unreviewed_bootstrap_is_not_executed(project, tmp_path):
    marker = tmp_path / "unchecked-bootstrap-ran"
    bootstrap = Path(project[1]["GNN_BOOTSTRAP"])
    bootstrap.write_bytes(bootstrap.read_bytes() + f"\n__import__('pathlib').Path({str(marker)!r}).touch()\n".encode())
    _failure(_run(project), "bootstrap-hash-mismatch")
    assert not marker.exists()


@pytest.mark.parametrize("name,code", [
    ("GNN_BOOTSTRAP", "bootstrap-unavailable"),
    ("GNN_SOURCE_MANIFEST", "source-manifest-unavailable"),
])
def test_missing_independent_resource_cannot_qualify(project, name, code):
    project[1].pop(name)
    _failure(_run(project), code)


def test_manifest_bytes_are_independently_frozen_not_reconstructed(project):
    manifest = Path(project[1]["GNN_SOURCE_MANIFEST"])
    manifest.write_bytes(manifest.read_bytes() + b" ")
    _failure(_run(project), "source-manifest-hash-mismatch")


def test_same_version_with_a_different_commit_is_not_admitted(project):
    pin_path = project[0] / ".github" / "gnn-pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    pin["revision"] = "0" * 40
    pin_path.write_text(json.dumps(pin), encoding="utf-8")
    _failure(_run(project), "source-pin-mismatch")


@pytest.mark.parametrize("member", ["__init__.py", "parsers/basic.py", "type_checker/checking/core.py"])
def test_corrupt_real_member_is_rejected_before_its_code_executes(project, tmp_path, inputs, member):
    package = _mutable_package(project, tmp_path, inputs)
    marker = tmp_path / "unchecked-member-ran"
    path = package / member
    path.write_bytes(path.read_bytes() + f"\n__import__('pathlib').Path({str(marker)!r}).touch()\n".encode())
    _failure(_run(project), "source-content-mismatch")
    assert not marker.exists()


@pytest.mark.parametrize("operation", ["missing", "extra"])
def test_full_inventory_rejects_unimported_missing_or_extra_members(project, tmp_path, inputs, operation):
    package = _mutable_package(project, tmp_path, inputs)
    manifest = json.loads(Path(project[1]["GNN_SOURCE_MANIFEST"]).read_text(encoding="utf-8"))
    if operation == "missing":
        member = next(name for name in sorted(manifest["files"]) if not name.endswith(".py"))
        (package / member.removeprefix("src/gnn/")).unlink()
    else:
        (package / "unreviewed-content.txt").write_text("not in the independent inventory\n", encoding="utf-8")
    _failure(_run(project), "source-content-mismatch")


def test_clean_source_cannot_fallback_after_installed_origin_refusal(project, tmp_path, inputs):
    package = _mutable_package(project, tmp_path, inputs)
    project[1]["GNN_ORIGIN_MODE"] = "installed"
    # Resolve a real, content-identical copy which no installed distribution owns.
    # No fabricated dist-info or PEP 610 metadata is supplied.
    prelude = f"sys.path.insert(0, {str(package.parent)!r})"
    _failure(_run(project, prelude=prelude), "source-origin-unavailable", "source-origin-mismatch")


def test_source_selection_rejects_foreign_import_resolution_before_execution(project, tmp_path, inputs):
    shadow = _mutable_package(project, tmp_path, inputs)
    project[1]["GNN_PACKAGE_ROOT"] = str(inputs["GNN_PACKAGE_ROOT"])
    marker = tmp_path / "shadow-import-ran"
    entry = shadow / "__init__.py"
    entry.write_bytes(entry.read_bytes() + f"\n__import__('pathlib').Path({str(marker)!r}).touch()\n".encode())
    prelude = f"""
        import importlib.abc
        import importlib.util
        class ForeignSourceFinder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'gnn':
                    return importlib.util.spec_from_file_location(
                        fullname, {str(entry)!r}, submodule_search_locations=[{str(shadow)!r}])
        sys.meta_path.insert(0, ForeignSourceFinder())
    """
    _failure(_run(project, prelude=prelude), "source-origin-mismatch")
    assert not marker.exists()


@pytest.mark.parametrize("target", ["package", "bootstrap", "manifest"])
def test_verdict_completion_revalidates_source_and_independent_inputs(project, tmp_path, inputs, target):
    package = _mutable_package(project, tmp_path, inputs)
    if target == "package":
        victim = package / "utils" / "__init__.py"
        code = "source-content-mismatch"
    else:
        key = "GNN_BOOTSTRAP" if target == "bootstrap" else "GNN_SOURCE_MANIFEST"
        victim = Path(project[1][key])
        code = "bootstrap-hash-mismatch" if target == "bootstrap" else "source-manifest-hash-mismatch"
    marker = tmp_path / "real-checker-completed"
    prelude = f"""
        def mutate_after_real_checker(frame, event, result):
            if (event == 'return' and frame.f_code.co_name == 'validate_gnn_files'
                    and frame.f_code.co_filename == {str(package / 'type_checker/checking/core.py')!r}):
                sys.setprofile(None)
                victim = Path({str(victim)!r})
                victim.write_bytes(victim.read_bytes() + b'\\n')
                Path({str(marker)!r}).touch()
        sys.setprofile(mutate_after_real_checker)
    """
    _failure(_run(project, prelude=prelude), code)
    assert marker.exists(), "the real GNN checker must execute before the lifetime mutation"


@pytest.mark.parametrize("target", ["bootstrap", "parser"])
def test_checked_source_execution_ignores_unchecked_cached_bytecode(project, tmp_path, inputs, target):
    marker = tmp_path / "unchecked-bytecode-ran"
    if target == "bootstrap":
        checked = Path(project[1]["GNN_BOOTSTRAP"])
    else:
        package = _mutable_package(project, tmp_path, inputs)
        checked = package / "parsers" / "basic.py"
    payload = tmp_path / "unchecked-payload.py"
    payload.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('unchecked bytecode executed')\n", encoding="utf-8")
    cache = Path(importlib.util.cache_from_source(str(checked)))
    cache.parent.mkdir(exist_ok=True)
    py_compile.compile(
        str(payload), cfile=str(cache), doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )
    _success(_run(project))
    assert not marker.exists()


def test_already_imported_real_gnn_cannot_open_another_verdict_lifetime(project):
    prelude = """
        import os
        adapter = runpy.run_path(sys.argv[0])
        bootstrap = adapter['_load_bootstrap'](Path(os.environ['GNN_BOOTSTRAP']))
        package = Path(os.environ['GNN_PACKAGE_ROOT'])
        sys.path.insert(0, str(package.parent))
        with bootstrap.qualified_source(
                bootstrap.read_pin(project / '.github/gnn-pin.json'),
                manifest=Path(os.environ['GNN_SOURCE_MANIFEST']).read_bytes(),
                manifest_sha256=adapter['MANIFEST_SHA256'],
                package_root=package, origin_mode='source'):
            import gnn
    """
    _failure(_run(project, prelude=prelude), "source-already-imported")


def test_invalid_real_document_never_reports_a_verified_verdict(project):
    (project[0] / "invalid.gnn.md").write_text("This is not a GNN model.\n", encoding="utf-8")
    _failure(_run(project), "parser-rejected", "syntax-rejected")


def test_source_mode_requires_explicit_root_and_cannot_install(project):
    project[1].pop("GNN_PACKAGE_ROOT")
    _failure(_run(project), "source-root-invalid")
    project[1]["GNN_PACKAGE_ROOT"] = str(project[0] / "not-selected")
    project[1]["GNN_NO_INSTALL"] = "0"
    _failure(_run(project), "source-root-invalid")


def test_bootstrap_executes_the_checked_buffer_not_a_later_file_read(project, tmp_path):
    bootstrap = Path(project[1]["GNN_BOOTSTRAP"])
    marker = tmp_path / "replacement-bootstrap-ran"
    prelude = f"""
        def replace_after_checked_read(frame, event, content):
            if (event == 'return' and frame.f_code.co_name == '_checked_resource'
                    and frame.f_locals.get('label') == 'bootstrap'):
                sys.setprofile(None)
                path = Path({str(bootstrap)!r})
                payload = "\\n__import__('pathlib').Path({str(marker)!r}).touch()\\n"
                path.write_bytes(content + payload.encode())
        sys.setprofile(replace_after_checked_read)
    """
    _failure(_run(project, prelude=prelude), "bootstrap-hash-mismatch")
    assert not marker.exists()


def test_real_parser_and_verdict_calls_stay_inside_the_admitted_lifetime(project):
    prelude = """
        def require_live_admission(frame, event, result):
            name = frame.f_globals.get('__name__', '')
            if event == 'call' and (name == 'gnn' or name.startswith('gnn.')):
                bootstrap = sys.modules.get('_iris_reviewed_gnn_bootstrap')
                if bootstrap is None or bootstrap._ACTIVE_SOURCE is None:
                    raise RuntimeError('real GNN code executed outside qualified_source')
        sys.setprofile(require_live_admission)
    """
    _success(_run(project, prelude=prelude))


def test_local_exemplar_suffix_cannot_turn_type_checking_into_an_empty_success(project, tmp_path):
    original = Path(project[1]["GNN_EXEMPLAR"])
    exemplar = original.with_suffix(".txt")
    original.rename(exemplar)
    project[1]["GNN_EXEMPLAR"] = str(exemplar)
    marker = tmp_path / "real-per-file-type-check-ran"
    prelude = f"""
        def observe_actual_type_check(frame, event, result):
            if (event == 'call' and frame.f_code.co_name == 'validate_single_gnn_file'
                    and frame.f_globals.get('__name__') == 'gnn.type_checker.checking.core'):
                Path({str(marker)!r}).touch()
        sys.setprofile(observe_actual_type_check)
    """
    report = _success(_run(project, prelude=prelude))
    assert report["source"] == "local-exemplar"
    assert marker.exists(), "a real per-file type check is required, not the empty-selection warning sentinel"
