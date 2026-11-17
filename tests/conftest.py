"""Shared pytest configuration: make the repository root importable.

Tests marked ``gnn_resources`` need the independently reviewed GNN inputs
(GNN_BOOTSTRAP, GNN_SOURCE_MANIFEST, GNN_PACKAGE_ROOT, GNN_EXEMPLAR). They are
deselected — not skipped — unless ``--gnn-admission`` is given, which the
``admission`` gate arm passes. Under that option a missing input remains a failed
prerequisite, never a skip.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GNN_RESOURCES_MARKER = "gnn_resources"


def pytest_addoption(parser):
    parser.addoption(
        "--gnn-admission",
        action="store_true",
        default=False,
        help="select the gnn_resources tests; their reviewed GNN_* inputs become required",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--gnn-admission"):
        return
    selected, deselected = [], []
    for item in items:
        (deselected if item.get_closest_marker(GNN_RESOURCES_MARKER) else selected).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected
