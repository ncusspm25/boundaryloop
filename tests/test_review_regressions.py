from __future__ import annotations

import copy
from dataclasses import replace
from unittest.mock import patch

import pytest

from boundaryloop import decisions
from boundaryloop.config import config_hash, validate
from boundaryloop.demo import contract
from boundaryloop.errors import BoundaryError, SecurityError
from boundaryloop.orchestrator import Controller
from boundaryloop.security import actor_id, relative_name
from boundaryloop.state import Store


@pytest.mark.parametrize(
    "name",
    [".venv/x.py", "node_modules/x.js", "build/x.py", "COM1.txt", "nul.py", "lpt9", ".git/HEAD"],
)
def test_excluded_and_device_paths_cannot_be_worker_targets(name):
    with pytest.raises(SecurityError):
        relative_name(name)


def test_verification_script_cannot_be_editable():
    with pytest.raises(BoundaryError, match="verification command file"):
        replace(contract(), allowed_files=("verify.py",), forbidden_files=())


def test_case_insensitive_forbidden_overlap():
    with pytest.raises(BoundaryError, match="overlap"):
        replace(contract(), forbidden_files=("PARSER.PY",))


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1])
def test_invalid_budget_cannot_disable_limits(project, value):
    cfg = {**project[1], "max_seconds": value}
    with pytest.raises(BoundaryError):
        validate(cfg)


def test_fixed_budget_extension_can_resume(project):
    root, cfg = project
    cfg["max_calls"] = 1
    run = Controller(root).start(contract(), cfg)
    id_ = run["decisions"][0]["decision_id"]
    with patch("boundaryloop.decisions.confirm", return_value=actor_id()):
        decision = decisions.act(Store(root), id_, "approve", "extend-once", root)
    assert decision["approved_scope"] == ["4 additional calls", "300 additional seconds"]
    resumed = Controller(root).resume(run["run_id"], cfg)
    assert resumed["state"] == "COMPLETED"
    assert resumed["limits"]["max_calls"] == 5


def test_config_material_change_invalidates_suspended_execution(project):
    root, cfg = project
    run = Controller(root).start(contract(), cfg, "human")
    id_ = run["decisions"][0]["decision_id"]
    with patch("boundaryloop.decisions.confirm", return_value=actor_id()):
        decisions.act(Store(root), id_, "approve", "allow-files", root)
    different = copy.deepcopy(cfg)
    different["worker"]["model"] = "different-worker"
    assert config_hash(different) != config_hash(cfg)
    resumed = Controller(root).resume(run["run_id"], different)
    assert resumed["state"] == "BLOCKED"
    assert resumed["decisions"][0]["status"] == "INVALIDATED"


def test_human_cannot_override_forbidden_verifier(project):
    root, cfg = project
    run = Controller(root).start(contract(), cfg, "human")
    with pytest.raises(SecurityError, match="immutable forbidden"):
        decisions.create(run, "Weaken test", [], ["verify.py"], ["Remove assertion"])


def test_cancellation_clears_pending_queue(project):
    root, cfg = project
    run = Controller(root).start(contract(), cfg, "human")
    cancelled = Controller(root).cancel(run["run_id"])
    assert cancelled["state"] == "CANCELLED"
    assert all(d["status"] == "CANCELLED" for d in cancelled["decisions"])


def test_local_interrupt_stops_without_escalation(project):
    root, cfg = project

    class Interrupted:
        def invoke(self, *args, **kwargs):
            raise KeyboardInterrupt

    run = Controller(root, {"worker": Interrupted()}).start(contract(), cfg)
    assert run["state"] == "CANCELLED"
    assert len(run["calls"]) == 1 and not run["tickets"]
    assert run["checkpoint"]["label"] == "initial"
