"""Human Decision Firewall: interactive OS identity, exact scope, revocation and audit."""

from __future__ import annotations

import sys
import textwrap
import uuid
from pathlib import Path

from .contracts import Contract
from .errors import SecurityError, StateError
from .security import actor_id, digest, relative_name
from .state import Store, event, now, transition


def binding(run: dict) -> str:
    return digest(
        {
            "contract": run["contracts"][-1],
            "checkpoint": run["checkpoint"]["hash"],
            "config": run["config_hash"],
            "task": run["task_id"],
        }
    )


def create(
    run: dict,
    reason: str,
    evidence: list[str],
    requested_files: list[str] | None = None,
    steps: list[str] | None = None,
    decision_type: str = "scope",
) -> dict:
    files = sorted(set(relative_name(n) for n in (requested_files or [])))
    contract = Contract.from_dict(run["contracts"][-1])
    if set(files) & set(contract.forbidden_files):
        raise SecurityError(
            "Proposal includes immutable forbidden files; start a new reviewed task"
        )
    proposal = {"files": files, "steps": steps or [], "decision_type": decision_type}
    proposal_hash = digest(proposal)
    for old in run["decisions"]:
        if old["proposal_hash"] == proposal_hash and old["binding"] == binding(run):
            if old["status"] == "REJECTED":
                raise SecurityError("Rejected proposal cannot be reintroduced as authorization")
            if old["status"] in {"PENDING", "DEFERRED"}:
                return old
    options = {"stop": "Cancel this task and retain all local files"}
    if files:
        options = {
            "allow-files": "Allow only the listed file-scope extension; keep validators",
            "keep-contract": "Reject the extension; resume within the existing contract",
            **options,
        }
    if decision_type == "budget":
        options = {
            "extend-once": "Add exactly 4 model calls and 300 seconds to this run",
            **options,
        }
    decision = {
        "decision_id": uuid.uuid4().hex[:12],
        "run_id": run["run_id"],
        "task_id": run["task_id"],
        "contract_version": contract.contract_version,
        "decision_type": decision_type,
        "selected_option": None,
        "approved_scope": [],
        "actor": None,
        "timestamp": now(),
        "reason": reason,
        "affected_files": files,
        "expiration_or_invalidation_conditions": (
            "Material contract, checkpoint, task or configuration change; explicit revocation"
        ),
        "binding": binding(run),
        "proposal_hash": proposal_hash,
        "proposal": proposal,
        "status": "PENDING",
        "evidence": evidence[-4:],
        "options": options,
        "recommendation": "keep-contract" if files else "stop",
        "consequences": "Only listed paths expand; verification and operations stay fixed",
        "risk": "Provider calls may incur charges; proposed code needs the existing verification",
        "safe_default": "Remain HUMAN_REQUIRED; no further model calls or edits",
        "priority": 10 if decision_type == "budget" else 20,
        "tried": [r["VALIDATOR_OBSERVED_STATUS"] for r in run["receipts"][-3:]],
    }
    if decision_type == "budget":
        decision["consequences"] = (
            "Allowance adds exactly 4 calls and 300 seconds; file scope stays fixed"
        )
    run["decisions"].append(decision)
    event(run, "decision_required", decision_id=decision["decision_id"], reason=reason)
    return decision


def invalidate(run: dict) -> None:
    for decision in run["decisions"]:
        if decision["status"] in {"APPROVED", "PENDING", "DEFERRED"} and (
            decision.get("valid_for", decision["binding"]) != binding(run)
        ):
            decision["status"] = "INVALIDATED"
            decision["invalidated_at"] = now()


def confirm(decision_id: str, option: str) -> str:
    """A pipe, env var or model-generated approval file cannot satisfy this path."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SecurityError(
            "Approval requires an interactive local terminal; decision remains pending"
        )
    phrase = f"{decision_id} {option}"
    tty = "CONIN$" if sys.platform == "win32" else "/dev/tty"
    try:
        with open(tty, encoding="utf-8") as stream:
            print(f"Confirm this exact decision by typing: {phrase}", flush=True)
            answer = stream.readline().rstrip("\r\n")
    except OSError as exc:
        raise SecurityError("No verified interactive terminal available") from exc
    if answer != phrase:
        raise SecurityError("Confirmation did not match; decision remains pending")
    return actor_id()


def find(store: Store, id_: str) -> tuple[dict, dict]:
    for run in store.all("run"):
        for decision in run["decisions"]:
            if decision["decision_id"] == id_:
                return run, decision
    raise StateError(f"Unknown decision: {id_}")


def act(
    store: Store, id_: str, action: str, option: str | None, root: Path, reason: str = ""
) -> dict:
    from .checkpoints import assert_unchanged

    with store.lock():
        run, decision = find(store, id_)
        if run["owner"] != actor_id():
            raise SecurityError("Unauthorized actor: only the OS run owner may decide")
        if action == "revoke":
            if decision["status"] != "APPROVED":
                raise StateError("Only a recorded approval can be revoked")
            decision["revoked_by"] = confirm(id_, "revoke")
            decision["status"] = "REVOKED"
            decision["revoked_at"] = now()
            # Revocation never rolls back user work. No further execution is authorized.
            if run["state"] not in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}:
                transition(
                    run, "BLOCKED", "Approval revoked; create a new reviewed task to continue"
                )
            store.save_run(run)
            return decision
        if decision["status"] not in {"PENDING", "DEFERRED"}:
            raise StateError("Decision is no longer pending")
        if run["state"] != "HUMAN_REQUIRED":
            raise StateError("Run is not waiting for a decision")
        if decision["binding"] != binding(run):
            decision["status"] = "INVALIDATED"
            store.save_run(run)
            raise SecurityError("Decision context changed; obsolete approval rejected")
        assert_unchanged(root, run["checkpoint"])
        selected = option if action == "approve" else action
        if action == "approve" and selected not in decision["options"]:
            raise SecurityError("Option is not supported by this decision card")
        actor = confirm(id_, str(selected))
        if actor != run["owner"]:
            raise SecurityError("Interactive actor differs from the OS run owner")
        decision.update(
            actor=actor,
            selected_option=selected,
            timestamp=now(),
            reason=reason or decision["reason"],
        )
        if action == "defer":
            decision["status"] = "DEFERRED"
        elif action == "reject" or selected == "keep-contract":
            decision["status"] = "REJECTED"
            run["decision_outcome"] = "Rejected scope extension; preserve original contract"
            run["next_phase"] = "diagnose"
            if decision["decision_type"] == "scope" and decision["affected_files"]:
                transition(run, "RESUMABLE", "Human rejected proposal; original boundary preserved")
            else:
                transition(run, "BLOCKED", "Human declined authority needed to continue")
        elif selected == "stop":
            decision["status"] = "REJECTED"
            transition(run, "CANCELLED", "Human selected stop")
        elif selected == "extend-once":
            run["limits"]["max_calls"] += 4
            run["limits"]["max_seconds"] += 300
            decision["status"] = "APPROVED"
            decision["approved_scope"] = ["4 additional calls", "300 additional seconds"]
            decision["valid_for"] = binding(run)
            transition(run, "RESUMABLE", "Human approved exact budget extension")
        elif selected == "allow-files":
            contract = Contract.from_dict(run["contracts"][-1])
            revised = contract.revision(
                steps=decision["proposal"]["steps"],
                allowed_files=sorted(set(contract.allowed_files) | set(decision["affected_files"])),
            )
            run["contracts"].append(revised.to_dict())
            invalidate(run)
            decision["status"] = "APPROVED"
            decision["approved_scope"] = decision["affected_files"]
            decision["valid_for"] = binding(run)
            run["repair_steps"] = decision["proposal"]["steps"]
            run["decision_outcome"] = "Approved only the listed file-scope extension"
            run["scope_approval_required"] = id_
            run["next_phase"] = "worker"
            transition(run, "RESUMABLE", "Human approved scoped contract revision")
        else:
            raise SecurityError("Unsupported decision action")
        event(run, "human_decision", decision_id=id_, status=decision["status"], actor=actor)
        store.save_run(run)
        return decision


def card(decision: dict) -> str:
    def concise(value: str, width: int = 180) -> str:
        return textwrap.shorten(value, width=width, placeholder=" ...")

    options = "\n".join(f"  {key}: {value}" for key, value in decision["options"].items())
    title = (
        "DECISION REQUIRED" if decision["status"] in {"PENDING", "DEFERRED"} else "DECISION CARD"
    )
    return (
        f"{title}  {decision['decision_id']}  [{decision['status']}]\n"
        f"Task: {decision['task_id']}  Run: {decision['run_id']}\n"
        f"Why stopped: {concise(decision['reason'])}\n"
        f"Evidence: {concise('; '.join(decision['evidence']) or 'No verifier has run yet', 260)}\n"
        f"Already tried: {', '.join(decision['tried']) or 'No repair attempts'}\n"
        f"Files: {concise(', '.join(decision['affected_files']) or 'No file-scope change')}\n"
        f"Choose:\n{options}\n"
        f"Recommendation: {decision['recommendation']}\n"
        f"Consequences: {decision['consequences']}\n"
        f"Cost/risk: {decision['risk']}\n"
        f"No response: {decision['safe_default']}\n"
        f"Full details: boundaryloop --json decision show {decision['decision_id']}"
    )
