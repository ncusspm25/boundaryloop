"""A finite controller: proposals, independent evidence, scoped authority, safe stop."""

from __future__ import annotations

import difflib
import json
import platform
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from . import checkpoints, decisions
from . import config as configuration
from .adapters import make_adapter
from .adapters.base import Adapter, validate_response
from .boundary_detector import Action, detect, fingerprint
from .contracts import Contract
from .errors import BoundaryError, ProviderError, SecurityError
from .memory import record_profile, remember
from .security import actor_id, clean, digest, redact, safe_path
from .state import TERMINAL, Store, event, now, transition
from .validators import verify


class Controller:
    def __init__(
        self,
        root: Path,
        adapters: dict[str, Adapter] | None = None,
        notify: Callable[[str], None] | None = None,
    ):
        self.root = root.resolve()
        self.store = Store(self.root)
        self.adapters = adapters or {}
        self.notify = notify or (lambda message: None)

    def start(
        self,
        contract: Contract,
        config: dict,
        scenario: str = "repair",
        category: str = "code-modification",
    ) -> dict:
        config = configuration.validate(config)
        if redact(json.dumps(contract.to_dict())) != json.dumps(contract.to_dict()):
            raise SecurityError("Contract appears to contain a secret")
        if (
            any(config[role]["provider"] != "mock" for role in ("worker", "architect"))
            and not (config["external_context_authorized"])
        ):
            raise SecurityError(
                "Authorize external_context_authorized before sending code to a provider"
            )
        with self.store.lock():
            active = [r for r in self.store.all("run") if r["state"] not in TERMINAL]
            if active:
                raise BoundaryError(
                    "An unfinished run owns this workspace; resume or cancel it first"
                )
            for name in contract.allowed_files + contract.forbidden_files:
                safe_path(self.root, name)
            cp = checkpoints.checkpoint(self.root, "initial")
            id_ = uuid.uuid4().hex[:12]
            run = {
                "schema_version": 1,
                "run_id": id_,
                "task_id": contract.task_id,
                "owner": actor_id(),
                "state": "CREATED",
                "created_at": now(),
                "events": [],
                "contracts": [contract.to_dict()],
                "checkpoint": cp,
                "checkpoints": [cp],
                "config": config,
                "config_hash": configuration.config_hash(config),
                "limits": {"max_calls": config["max_calls"], "max_seconds": config["max_seconds"]},
                "calls": [],
                "receipts": [],
                "tickets": [],
                "decisions": [],
                "attempts": 0,
                "failures_in_plan": 0,
                "replans": 0,
                "subtasks": [],
                "subtask_index": 0,
                "repair_steps": [],
                "decision_outcome": "",
                "elapsed_seconds": 0.0,
                "scenario": scenario,
                "category": category,
                "next_phase": "planning" if contract.difficulty == "hard" else "worker",
                "takeover": False,
                "baseline": [],
                "last_failure": None,
            }
            event(
                run,
                "created",
                difficulty=contract.difficulty,
                models={role: config[role] for role in ("architect", "worker")},
            )
            self.store.save_run(run)
            return self._execute(run)

    def resume(self, id_: str, config: dict | None = None) -> dict:
        with self.store.lock():
            run = self.store.get("run", id_)
            if run["owner"] != actor_id():
                raise SecurityError("Only the OS run owner may resume")
            if run["state"] in TERMINAL or run["state"] == "HUMAN_REQUIRED":
                return run  # Idempotent; approval never happens as a side effect of resume.
            if config is not None and configuration.config_hash(config) != run["config_hash"]:
                self._block(run, "Configuration changed since checkpoint; start a new reviewed run")
                decisions.invalidate(run)
                self.store.save_run(run)
                return run
            try:
                checkpoints.assert_unchanged(self.root, run["checkpoint"])
            except SecurityError as exc:
                self._block(run, str(exc))
                self.store.save_run(run)
                return run
            # A crashed in-flight provider call has an unknown outcome; do not call it again.
            if any(call["status"] == "IN_FLIGHT" for call in run["calls"]):
                self._block(run, "Interrupted provider call has unknown outcome; inspect evidence")
                self.store.save_run(run)
                return run
            if run["state"] not in {"CREATED", "RESUMABLE", "READY"}:
                self._block(
                    run, "Interrupted write/verification; reconciliation required, files retained"
                )
                self.store.save_run(run)
                return run
            event(run, "resumed", checkpoint_id=run["checkpoint"]["checkpoint_id"])
            return self._execute(run)

    def cancel(self, id_: str) -> dict:
        with self.store.lock():
            run = self.store.get("run", id_)
            if run["state"] not in TERMINAL:
                transition(run, "CANCELLED", "Local owner cancelled; files retained")
                for decision in run["decisions"]:
                    if decision["status"] in {"PENDING", "DEFERRED", "APPROVED"}:
                        decision["status"] = "CANCELLED"
                        decision["invalidated_at"] = now()
                self.store.save_run(run)
            return run

    def _block(self, run: dict, reason: str) -> None:
        transition(run, "BLOCKED", reason)
        for decision in run["decisions"]:
            if decision["status"] in {"PENDING", "DEFERRED", "APPROVED"}:
                decision["status"] = "INVALIDATED"
                decision["invalidated_at"] = now()
                decision["invalidation_reason"] = reason
        run["stop_reason"] = reason
        self.notify("BLOCKED: " + reason)

    def _human(
        self,
        run: dict,
        reason: str,
        requested: list[str] | None = None,
        steps: list[str] | None = None,
        kind: str = "scope",
    ) -> None:
        evidence = [ticket["ticket_id"] for ticket in run["tickets"][-2:]]
        evidence += [receipt["evidence_references"][0] for receipt in run["receipts"][-2:]]
        if run["receipts"]:
            for result in run["receipts"][-1]["verification_results"]:
                failures = [
                    line.strip()
                    for line in result["output"].splitlines()
                    if line.startswith(("FAIL:", "ERROR:", "AssertionError:"))
                ]
                evidence.extend(failures[:2])
        decisions.create(run, reason, evidence, requested, steps, kind)
        transition(run, "HUMAN_REQUIRED", reason)
        self.notify("HUMAN_REQUIRED: " + reason)

    def _remaining(self, run: dict) -> float:
        return max(0.0, run["limits"]["max_seconds"] - run["elapsed_seconds"])

    def _context(self, run: dict, phase: str) -> dict:
        contract = Contract.from_dict(run["contracts"][-1])
        files = {}
        total = 0
        for name in contract.allowed_files:
            path = safe_path(self.root, name)
            text = path.read_text(encoding="utf-8") if path.exists() else "<new file>"
            total += len(text.encode())
            if total > 128 * 1024:
                raise ProviderError("Authorized context exceeds 128 KiB; narrow the task")
            files[name] = redact(text)
        return clean(
            {
                "phase": phase,
                "contract": contract.to_dict(),
                "files": files,
                "ticket": run["tickets"][-1] if run["tickets"] else None,
                "last_verification": run["receipts"][-1]["verification_results"]
                if run["receipts"]
                else run["baseline"],
                "repair_steps": run["repair_steps"],
                "scenario": run["scenario"],
                "decision_outcome": run["decision_outcome"],
                "failure_memory": [
                    m
                    for m in self.store.all("memory")
                    if m.get("fingerprint") == run["last_failure"]
                ][-1:],
                "denied_proposals": [
                    d["proposal"]
                    for d in run["decisions"]
                    if d["status"] in {"REJECTED", "REVOKED"}
                ],
            }
        )

    def _call(self, run: dict, role: str, phase: str) -> dict | None:
        if len(run["calls"]) >= run["limits"]["max_calls"] or self._remaining(run) <= 0:
            self._human(run, "Model-call or time budget exhausted", kind="budget")
            return None
        spec = run["config"][role]
        call = {
            "role": role,
            "provider": spec["provider"],
            "model": spec["model"],
            "phase": phase,
            "timestamp": now(),
            "status": "IN_FLIGHT",
            "cost": None,
            "input_tokens": None,
            "output_tokens": None,
        }
        run["calls"].append(call)
        self.store.save_run(run)  # Charge the call before invoking an external process.
        self.notify(f"{role.upper()} [{spec['provider']} / {spec['model']}] {phase}")
        started = time.monotonic()
        try:
            adapter = self.adapters.get(role) or make_adapter(spec["provider"])
            timeout = min(run["config"]["provider_timeout_seconds"], self._remaining(run))
            value = validate_response(
                adapter.invoke(role, spec["model"], self._context(run, phase), timeout)
            )
            # Proposal content must remain intact for rejection, never silently redacted into code.
            value = {key: item if key == "files" else clean(item) for key, item in value.items()}
            call["status"] = "RETURNED"
            call.update(getattr(adapter, "last_usage", {}))
            call["provider_session_id"] = getattr(adapter, "last_session_id", None)
            return value
        except (ProviderError, OSError, ValueError) as exc:
            call["status"] = "ERROR"
            call["error"] = redact(str(exc))
            self._block(run, "Provider unavailable or invalid output: " + redact(str(exc)))
            return None
        finally:
            call["seconds"] = time.monotonic() - started
            run["elapsed_seconds"] += call["seconds"]
            self.store.save_run(run)

    def _verify(self, run: dict, contract: Contract) -> list[dict]:
        started = time.monotonic()
        results = verify(
            self.root,
            contract.verification_commands,
            run["config"]["validator"]["timeout_seconds"],
            self._remaining(run),
        )
        run["elapsed_seconds"] += time.monotonic() - started
        return results

    def _plan(self, run: dict) -> bool:
        transition(run, "PLANNING")
        value = self._call(run, "architect", "planning")
        if value is None:
            return False
        if value["action"] == "human":
            self._human(run, value["summary"], value["requested_files"], value["steps"])
            return False
        if value["action"] != "plan" or not value["subtasks"]:
            raise ProviderError("Architect must return bounded subtasks for a HARD task")
        parent = Contract.from_dict(run["contracts"][-1])
        tasks = []
        for index, task in enumerate(value["subtasks"]):
            if not set(task["allowed_files"]) <= set(parent.allowed_files):
                raise SecurityError("Architect plan exceeded approved scope")
            subtask = replace(
                parent,
                task_id=f"{parent.task_id}.{index + 1}",
                objective=task["objective"],
                allowed_files=tuple(task["allowed_files"]),
            )
            tasks.append(subtask.to_dict())
        run["subtasks"] = tasks
        run["contracts"].append(tasks[0])
        run["task_id"] = tasks[0]["task_id"]
        run["next_phase"] = "worker"
        transition(run, "READY")
        return True

    def _escalate(self, run: dict, reason: str, fp: str) -> None:
        evidence_hash = digest({"failure": fp, "files": run["checkpoint"]["hash"]})
        if any(ticket["evidence_hash"] == evidence_hash for ticket in run["tickets"]):
            self._block(run, "Identical escalation without new evidence; repetition blocked")
            return
        contract = Contract.from_dict(run["contracts"][-1])
        if run["replans"] >= contract.escalation_policy.get("max_replans", 2):
            self._human(
                run, "Strong replan budget exhausted; requirements need human review", kind="replan"
            )
            return
        receipt = run["receipts"][-1] if run["receipts"] else None
        ticket = {
            "ticket_id": uuid.uuid4().hex[:12],
            "task_id": run["task_id"],
            "contract": contract.to_dict(),
            "unresolved_issue": reason,
            "evidence_hash": evidence_hash,
            "fingerprint": fp,
            "evidence_references": receipt["evidence_references"]
            if receipt
            else ["worker_request"],
            "failed_attempts": [
                {"attempt": r["attempt"], "status": r["FINAL_STATUS"], "strategy": r["strategy"]}
                for r in run["receipts"][-3:]
            ],
            "code_differences": {
                "modified_files": receipt["modified_files"] if receipt else [],
                "checkpoint_hash": run["checkpoint"]["hash"],
                "diff": receipt.get("diff", "") if receipt else "",
            },
            "validator_output": receipt["verification_results"] if receipt else run["baseline"],
            "known_facts": [reason, "Verification policy has not been changed"],
            "open_questions": ["What constraint or bounded repair resolves this failure?"],
            "requested_decision": "Repair, replan, takeover, human decision, block or abort",
        }
        run["tickets"].append(ticket)
        transition(run, "ESCALATION_REQUIRED", reason)
        run["next_phase"] = "diagnose"
        self.notify(f"STOP: {reason}; checkpoint preserved; ticket {ticket['ticket_id']}")
        self.store.save_run(run)

    def _diagnose(self, run: dict) -> bool:
        contract = Contract.from_dict(run["contracts"][-1])
        if run["replans"] >= contract.escalation_policy.get("max_replans", 2):
            self._human(run, "Strong replan budget exhausted", kind="replan")
            return False
        transition(run, "DIAGNOSING")
        value = self._call(run, "architect", "diagnosis")
        if value is None:
            return False
        run["replans"] += 1
        event(run, "diagnosis", result=value)
        if value["action"] in {"block", "abort"}:
            transition(
                run, "BLOCKED" if value["action"] == "block" else "CANCELLED", value["summary"]
            )
            return False
        if value["action"] == "human" or set(value["requested_files"]) - set(
            contract.allowed_files
        ):
            self._human(run, value["summary"], value["requested_files"], value["steps"])
            return False
        if (
            value["action"] not in {"repair", "takeover", "plan"}
            or not value["steps"]
            or not (value["stop_conditions"])
        ):
            raise ProviderError("A repair needs concrete steps and stop conditions")
        if value["files"]:
            raise SecurityError(
                "Diagnosis cannot apply implementation edits; use a bounded takeover"
            )
        revised = contract.revision(steps=value["steps"] + value["stop_conditions"])
        run["contracts"].append(revised.to_dict())
        decisions.invalidate(run)
        run["repair_steps"] = value["steps"]
        run["takeover"] = value["action"] == "takeover"
        run["failures_in_plan"] = 0
        run["next_phase"] = "worker"
        transition(run, "RESUMABLE", value["summary"])
        self.store.save_run(run)
        transition(run, "READY")
        return True

    def _worker(self, run: dict) -> bool:
        contract = Contract.from_dict(run["contracts"][-1])
        if run.get("scope_approval_required"):
            approval = next(
                d for d in run["decisions"] if d["decision_id"] == run["scope_approval_required"]
            )
            if approval["status"] != "APPROVED" or approval["valid_for"] != decisions.binding(run):
                raise SecurityError("Scope approval invalidated; no further edits permitted")
        transition(run, "RUNNING")
        role = "architect" if run["takeover"] else "worker"
        value = self._call(run, role, "implementation")
        if value is None:
            return False
        if value["action"] in {"escalate", "human"}:
            self._escalate(run, value["summary"], digest({"worker_issue": value["summary"]}))
            return True
        if value["action"] != "patch":
            raise ProviderError("Implementation must return patch or explicit escalation")
        run["attempts"] += 1
        self.store.save_run(
            run
        )  # Durable pre-write journal: crash never silently overwrites drift.
        before = {}
        for item in value["files"]:
            if item["path"] in contract.allowed_files:
                path = safe_path(self.root, item["path"])
                before[item["path"]] = path.read_text(encoding="utf-8") if path.exists() else ""
        modified = checkpoints.apply_files(
            self.root,
            value["files"],
            contract.allowed_files,
            contract.forbidden_files,
            run["checkpoint"],
        )
        cp = checkpoints.checkpoint(self.root, f"attempt-{run['attempts']}")
        run["checkpoint"] = cp
        run["checkpoints"].append(cp)
        # Expected, authorized writes are progress within this approval. External drift is
        # checked separately; contract/config changes still invalidate it.
        for approval in run["decisions"]:
            if approval["status"] == "APPROVED":
                approval["valid_for"] = decisions.binding(run)
        decisions.invalidate(run)
        transition(run, "VERIFYING")
        self.store.save_run(run)
        results = self._verify(run, contract)
        # Verifiers may create output caches but cannot silently modify source/policy files.
        checkpoints.assert_unchanged(self.root, cp)
        statuses = {r["status"] for r in results}
        observed = (
            "PASS"
            if statuses == {"PASS"}
            else ("UNVERIFIED" if statuses & {"UNAVAILABLE", "TIMEOUT"} or not results else "FAIL")
        )
        receipt = {
            "task_id": run["task_id"],
            "worker_model": run["config"][role]["model"],
            "contract_version": contract.contract_version,
            "modified_files": modified,
            "verification_commands": contract.verification_commands,
            "verification_results": results,
            "evidence_references": [f"run:{run['run_id']}/attempt:{run['attempts']}"],
            "unresolved_issues": [] if observed == "PASS" else [value["summary"], observed],
            "WORKER_CLAIMED_STATUS": value["claimed_status"],
            "VALIDATOR_OBSERVED_STATUS": observed,
            "FINAL_STATUS": observed,
            "final_status": observed,
            "checkpoint_id": cp["checkpoint_id"],
            "attempt": run["attempts"],
            "strategy": value["summary"],
            "diff": redact(
                "\n".join(
                    "".join(
                        difflib.unified_diff(
                            before.get(item["path"], "").splitlines(keepends=True),
                            item["content"].splitlines(keepends=True),
                            fromfile=item["path"],
                            tofile=item["path"],
                        )
                    )
                    for item in value["files"]
                )
            )[:16000],
            "execution_seconds": run["calls"][-1]["seconds"]
            + sum(r.get("seconds", 0) for r in results),
        }
        run["receipts"].append(receipt)
        event(run, "verification", attempt=run["attempts"], status=observed)
        self.notify(f"VALIDATOR: {observed} (attempt {run['attempts']})")
        if observed == "PASS":
            if run["last_failure"] and run["config"]["memory"]:
                remember(
                    self.store,
                    run["last_failure"],
                    {"strategy": value["summary"], "evidence": receipt["evidence_references"]},
                    success=True,
                )
            index = run["subtask_index"] + 1
            if index < len(run["subtasks"]):
                run["subtask_index"] = index
                next_contract = run["subtasks"][index]
                run["contracts"].append(next_contract)
                run["task_id"] = next_contract["task_id"]
                run["repair_steps"] = []
                run["failures_in_plan"] = 0
                transition(run, "READY", "Verified subtask complete")
                return True
            transition(run, "COMPLETED", "Independent verification passed")
            return False
        run["failures_in_plan"] += 1
        fp = fingerprint(results, contract.allowed_files, platform.python_version())
        run["last_failure"] = fp
        if run["config"]["memory"]:
            remember(
                self.store,
                fp,
                {"strategy": value["summary"], "evidence": receipt["evidence_references"]},
            )
        action = detect(
            signal="unavailable" if observed == "UNVERIFIED" else "failure",
            failures=run["failures_in_plan"],
            retry_budget=contract.retry_budget,
            previous_pass=bool(run["baseline"])
            and all(r["status"] == "PASS" for r in run["baseline"]),
        )
        if action == Action.RETRY:
            self.notify("RETRY: one bounded repair remains before escalation")
        else:
            self._escalate(
                run,
                "Verification failed; bounded local attempts exhausted"
                if observed == "FAIL"
                else "Required verification tool unavailable",
                fp,
            )
        return True

    def _execute(self, run: dict) -> dict:
        try:
            if not run["baseline"]:
                run["baseline"] = self._verify(run, Contract.from_dict(run["contracts"][-1]))
                checkpoints.assert_unchanged(self.root, run["checkpoint"])
            if run["state"] == "RESUMABLE":
                if run["next_phase"] == "diagnose":
                    transition(run, "ESCALATION_REQUIRED")
                elif run["next_phase"] == "planning":
                    transition(run, "PLANNING")
                else:
                    transition(run, "READY")
            if run["next_phase"] == "planning":
                if not self._plan(run):
                    return run
            elif run["state"] == "CREATED":
                transition(run, "READY")
            while run["state"] not in TERMINAL | {"HUMAN_REQUIRED"}:
                self.store.save_run(run)
                if run["state"] == "ESCALATION_REQUIRED":
                    if not self._diagnose(run):
                        break
                elif not self._worker(run):
                    break
        except KeyboardInterrupt:
            transition(
                run, "CANCELLED", "Interrupted by local operator; files and evidence retained"
            )
            for decision in run["decisions"]:
                if decision["status"] in {"PENDING", "DEFERRED", "APPROVED"}:
                    decision["status"] = "CANCELLED"
        except (SecurityError, ProviderError, BoundaryError, OSError, UnicodeError) as exc:
            self._block(run, redact(str(exc)))
        finally:
            self.store.save_run(run)
            if run["config"]["learning"]:
                record_profile(self.store, run)
        return run
