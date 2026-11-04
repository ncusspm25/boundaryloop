from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from unittest.mock import patch

import pytest

from boundaryloop import decisions
from boundaryloop.boundary_detector import Action, detect, fingerprint
from boundaryloop.config import validate
from boundaryloop.contracts import Contract
from boundaryloop.demo import contract
from boundaryloop.errors import BoundaryError, ProviderError, SecurityError, StateError
from boundaryloop.orchestrator import Controller
from boundaryloop.security import actor_id
from boundaryloop.state import Store, transition


def start(project, scenario="repair", difficulty="easy", adapters=None):
    root, cfg = project
    return Controller(root, adapters).start(contract(difficulty), cfg, scenario)


def pending(project):
    run = start(project, "human")
    assert run["state"] == "HUMAN_REQUIRED"
    return run, run["decisions"][0]["decision_id"]


def decide(project, id_, action, option=None):
    root, _ = project
    # Simulate only the authenticated terminal boundary; authorization/scope/state are real.
    with patch("boundaryloop.decisions.confirm", return_value=actor_id()):
        return decisions.act(Store(root), id_, action, option, root)


def test_01_easy_starts_worker(project):
    run = start(project, "success")
    assert run["calls"][0]["role"] == "worker"


def test_02_hard_starts_architect(project):
    run = start(project, difficulty="hard")
    assert run["calls"][0]["role"] == "architect"
    assert run["calls"][0]["phase"] == "planning"
    assert run["subtasks"] and run["state"] == "COMPLETED"


def test_03_verified_completion(project):
    run = start(project, "success")
    assert run["state"] == "COMPLETED"
    receipt = run["receipts"][-1]
    assert receipt["FINAL_STATUS"] == receipt["VALIDATOR_OBSERVED_STATUS"] == "PASS"
    assert all(r["exit_code"] == 0 for r in receipt["verification_results"])
    assert "isinstance" in (project[0] / "parser.py").read_text()


def test_04_worker_claim_is_not_pass(project):
    run = start(project)
    assert run["receipts"][0]["WORKER_CLAIMED_STATUS"] == "COMPLETED"
    assert run["receipts"][0]["FINAL_STATUS"] == "FAIL"


def test_05_repeated_failure_stops_before_third_worker(project):
    run = start(project)
    assert [c["role"] for c in run["calls"]] == ["worker", "worker", "architect", "worker"]
    assert len(run["tickets"]) == 1
    assert len(run["tickets"][0]["failed_attempts"]) == 2
    assert run["tickets"][0]["validator_output"][0]["exit_code"] != 0


def test_06_missing_spec_escalates(project):
    run = start(project, "missing_spec")
    assert run["calls"][1]["role"] == "architect"
    assert "Missing critical requirement" in run["tickets"][0]["unresolved_issue"]
    assert len(run["calls"]) < 8


def test_07_unauthorized_patch_is_all_or_nothing(project):
    original = (project[0] / "parser.py").read_text()
    run = start(project, "unauthorized")
    assert run["state"] == "BLOCKED"
    assert (project[0] / "parser.py").read_text() == original
    assert not (project[0] / "tests.py").exists()


def test_08_architect_repair_revises_contract(project):
    run = start(project)
    assert len(run["contracts"]) == 2
    assert run["contracts"][-1]["contract_version"] == 2
    assert (
        run["contracts"][0]["verification_commands"]
        == run["contracts"][-1]["verification_commands"]
    )


def test_09_resume_after_scoped_approval(project):
    root, cfg = project
    run, id_ = pending(project)
    cp = run["checkpoint"]["checkpoint_id"]
    decision = decide(project, id_, "approve", "allow-files")
    assert decision["approved_scope"] == ["api.py"]
    resumed = Controller(root).resume(run["run_id"], cfg)
    assert resumed["state"] == "COMPLETED"
    assert any(e.get("checkpoint_id") == cp for e in resumed["events"] if e["kind"] == "resumed")


def test_10_strong_takeover(project):
    run = start(project, "takeover")
    assert run["state"] == "COMPLETED"
    assert run["calls"][-1]["role"] == "architect"
    assert run["calls"][-1]["phase"] == "implementation"
    assert run["receipts"][-1]["worker_model"] == "mock-architect"


def test_11_human_firewall_blocks_without_approval(project):
    root, cfg = project
    before = (root / "api.py").read_text()
    run, _ = pending(project)
    again = Controller(root).resume(run["run_id"], cfg)
    assert again["state"] == "HUMAN_REQUIRED"
    assert len(again["calls"]) == 3
    assert (root / "api.py").read_text() == before


def test_12_scoped_approval_is_recorded(project):
    run, id_ = pending(project)
    result = decide(project, id_, "approve", "allow-files")
    assert result["actor"] == actor_id() and result["run_id"] == run["run_id"]
    assert result["status"] == "APPROVED" and result["approved_scope"] == ["api.py"]
    current = Store(project[0]).get("run", run["run_id"])
    assert "api.py" in current["contracts"][-1]["allowed_files"]
    assert "verify.py" not in current["contracts"][-1]["allowed_files"]


def test_13_rejection_preserves_contract(project):
    root, cfg = project
    run, id_ = pending(project)
    decide(project, id_, "reject")
    resumed = Controller(root).resume(run["run_id"], cfg)
    assert resumed["state"] == "COMPLETED"
    assert all("api.py" not in c["allowed_files"] for c in resumed["contracts"])


def test_14_deferred_decision_stays_pending(project):
    run, id_ = pending(project)
    result = decide(project, id_, "defer")
    assert result["status"] == "DEFERRED"
    assert Controller(project[0]).resume(run["run_id"])["state"] == "HUMAN_REQUIRED"


def test_15_material_contract_change_invalidates(project):
    root, _ = project
    run, id_ = pending(project)
    decide(project, id_, "approve", "allow-files")
    store = Store(root)
    run = store.get("run", run["run_id"])
    revised = Contract.from_dict(run["contracts"][-1]).revision(
        steps=["Different implementation plan"]
    )
    run["contracts"].append(revised.to_dict())
    decisions.invalidate(run)
    assert run["decisions"][0]["status"] == "INVALIDATED"
    store.save_run(run)
    resumed = Controller(root).resume(run["run_id"])
    assert resumed["state"] == "BLOCKED"


def test_16_unauthorized_actor_cannot_approve(project):
    _, id_ = pending(project)
    with patch("boundaryloop.decisions.actor_id", return_value="other-user"):
        with pytest.raises(SecurityError, match="Unauthorized actor"):
            decisions.act(Store(project[0]), id_, "approve", "allow-files", project[0])


def test_17_identical_escalation_is_blocked(project):
    run = start(project, "loop")
    assert run["state"] == "BLOCKED"
    assert "Identical escalation" in run["stop_reason"]
    assert run["replans"] == 1


def test_18_call_budget_requires_human(project):
    root, cfg = project
    cfg["max_calls"] = 1
    run = Controller(root).start(contract(), cfg)
    assert run["state"] == "HUMAN_REQUIRED"
    assert len(run["calls"]) == 1
    assert run["decisions"][0]["decision_type"] == "budget"
    assert run["decisions"][0]["options"]["extend-once"]


def test_18b_time_budget_requires_human(project):
    root, cfg = project
    cfg["max_seconds"] = 0.00001
    run = Controller(root).start(contract(), cfg)
    assert run["state"] == "HUMAN_REQUIRED" and not run["calls"]


def test_19_corrupt_state_detected(project):
    root, _ = project
    run = start(project, "success")
    with sqlite3.connect(Store(root).path) as db:
        db.execute("UPDATE records SET payload='{}' WHERE kind='run'")
    with pytest.raises(StateError, match="checksum"):
        Store(root).get("run", run["run_id"])


def test_19b_corrupt_database_fails_closed(tmp_path):
    state = tmp_path / ".boundaryloop"
    state.mkdir()
    (state / "state.sqlite3").write_bytes(b"not a database")
    with pytest.raises(StateError):
        Store(tmp_path)


def test_20_external_changes_preserved(project):
    root, cfg = project
    run, id_ = pending(project)
    decide(project, id_, "reject")
    (root / "parser.py").write_text("# external work\n")
    result = Controller(root).resume(run["run_id"], cfg)
    assert result["state"] == "BLOCKED"
    assert (root / "parser.py").read_text() == "# external work\n"


class Unavailable:
    def invoke(self, *args, **kwargs):
        raise ProviderError("test transport unavailable")


class Malformed:
    def invoke(self, *args, **kwargs):
        return {"action": "completed", "confidence": 1.0}


def test_21_unavailable_provider(project):
    run = start(project, adapters={"worker": Unavailable()})
    assert run["state"] == "BLOCKED" and not run["receipts"]
    assert run["calls"][0]["status"] == "ERROR"


def test_22_malformed_output(project):
    run = start(project, adapters={"worker": Malformed()})
    assert run["state"] == "BLOCKED" and "Malformed" in run["stop_reason"]


def test_23_secrets_redacted_from_state(project):
    root, cfg = project
    secret = "sk-" + "a" * 32

    class SecretFailure:
        def invoke(self, *args, **kwargs):
            raise ProviderError("transport error " + secret)

    run = Controller(root, {"worker": SecretFailure()}).start(contract(), cfg)
    assert secret not in json.dumps(Store(root).get("run", run["run_id"]))
    assert "[REDACTED]" in run["stop_reason"]


def test_24_verifier_unavailable_is_unverified(project):
    root, cfg = project
    task = replace(contract(), verification_commands=(("boundaryloop-tool-does-not-exist",),))
    run = Controller(root).start(task, cfg, "success")
    assert run["state"] != "COMPLETED"
    assert all(r["FINAL_STATUS"] == "UNVERIFIED" for r in run["receipts"])


def test_25_double_resume_is_idempotent(project):
    root, cfg = project
    run, id_ = pending(project)
    decide(project, id_, "reject")
    first = Controller(root).resume(run["run_id"], cfg)
    second = Controller(root).resume(run["run_id"], cfg)
    assert first["state"] == second["state"] == "COMPLETED"
    assert len(first["calls"]) == len(second["calls"])


def test_26_unsupported_model_configuration_is_error(project):
    class Unsupported:
        def invoke(self, role, model, context, timeout):
            raise ProviderError("model does not support requested configuration")

    run = start(project, adapters={"worker": Unsupported()})
    assert run["state"] == "BLOCKED"
    assert "configuration" in run["stop_reason"]


def test_27_enforced_mode_rejected(project):
    cfg = {**project[1], "mode": "enforced"}
    with pytest.raises(BoundaryError, match="UNSUPPORTED"):
        validate(cfg)


def test_28_failure_fingerprints_recur(project):
    start(project)
    items = Store(project[0]).all("memory")
    assert items and any(i["recurrence_count"] >= 2 for i in items)
    assert any(i["successful_strategies"] for i in items)


def test_29_fingerprint_does_not_authorize_fix(project):
    root, cfg = project
    store = Store(root)
    store.put(
        "memory",
        "unrelated",
        {"fingerprint": "unrelated", "successful_strategies": ["weaken tests"]},
    )
    run = Controller(root).start(contract(), cfg, "success")
    assert run["state"] == "COMPLETED"
    assert run["contracts"][0]["verification_commands"] == [["{python}", "verify.py"]] or (
        run["contracts"][0]["verification_commands"] == (("{python}", "verify.py"),)
    )
    assert "weaken tests" not in str(run["contracts"])


def test_30_final_state_cannot_bypass_validation():
    run = {"state": "VERIFYING", "events": [], "receipts": []}
    with pytest.raises(StateError, match="validator-observed"):
        transition(run, "COMPLETED")
    run["receipts"] = [
        {
            "FINAL_STATUS": "PASS",
            "VALIDATOR_OBSERVED_STATUS": "FAIL",
            "verification_results": [{"status": "FAIL"}],
        }
    ]
    with pytest.raises(StateError):
        transition(run, "COMPLETED")


def test_no_noninteractive_approval(project):
    _, id_ = pending(project)
    with patch("sys.stdin.isatty", return_value=False):
        with pytest.raises(SecurityError, match="interactive"):
            decisions.act(Store(project[0]), id_, "approve", "allow-files", project[0])


def test_rejected_action_cannot_be_reapproved(project):
    _, id_ = pending(project)
    decide(project, id_, "reject")
    with pytest.raises(StateError, match="no longer pending"):
        decide(project, id_, "approve", "allow-files")


def test_approval_cannot_authorize_unsupported_option(project):
    _, id_ = pending(project)
    with pytest.raises(SecurityError, match="not supported"):
        decide(project, id_, "approve", "deploy-everything")


def test_revocation_blocks_future_work(project):
    root, _ = project
    run, id_ = pending(project)
    decide(project, id_, "approve", "allow-files")
    decide(project, id_, "revoke")
    assert Controller(root).resume(run["run_id"])["state"] == "BLOCKED"


def test_concurrent_controller_lock(project):
    with Store(project[0]).lock():
        with pytest.raises(StateError, match="lock"):
            with Store(project[0]).lock():
                pytest.fail("second controller acquired the same workspace")


def test_crash_with_unknown_provider_outcome_blocks(project):
    root, _ = project
    run, id_ = pending(project)
    decide(project, id_, "reject")
    store = Store(root)
    run = store.get("run", run["run_id"])
    run["calls"].append({"status": "IN_FLIGHT"})
    store.save_run(run)
    assert Controller(root).resume(run["run_id"])["state"] == "BLOCKED"


def test_missing_new_evidence_does_not_loop():
    assert detect(signal="failure", failures=2) == Action.ESCALATE_STRONG
    assert detect(signal="failure", failures=1) == Action.RETRY
    assert detect(signal="failure", failures=1, previous_pass=True) == Action.ESCALATE_STRONG
    assert detect(signal="unauthorized") == Action.BLOCK


def test_normalized_traceback_fingerprint():
    a = [{"status": "FAIL", "output": 'File "/tmp/a", line 3\nValueError: bad'}]
    b = [{"status": "FAIL", "output": 'File "D:/b", line 8\nValueError: bad'}]
    assert fingerprint(a, ("parser.py",)) == fingerprint(b, ("parser.py",))


def test_memory_and_learning_can_be_disabled(project):
    root, cfg = project
    cfg.update(memory=False, learning=False)
    Controller(root).start(contract(), cfg)
    assert Store(root).all("memory") == Store(root).all("profile") == []


def test_profile_only_records_observed_outcomes(project):
    root, cfg = project
    cfg["learning"] = True
    run = Controller(root).start(contract(), cfg)
    samples = Store(root).all("profile")
    assert len(samples) == len(run["receipts"])
    assert sum(s["verified_success"] for s in samples) == 1
    assert sum(s["verified_failure"] for s in samples) == 2
