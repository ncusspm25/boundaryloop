"""Isolated offline policy comparisons. No simulated costs or model quality claims."""

from __future__ import annotations

import csv
import io
import json
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from .adapters.base import Adapter
from .adapters.mock import MockAdapter
from .demo import contract, prepare
from .errors import BoundaryError
from .orchestrator import Controller
from .security import atomic_write


class Baseline(MockAdapter):
    def __init__(self, strong_only: bool):
        self.strong_only = strong_only

    def invoke(self, role: str, model: str, context: dict, timeout: float) -> dict:
        if self.strong_only:
            context = {**context, "scenario": "success"}
        else:
            # This policy has an initial plan but no exception handoff.
            context = {**context, "scenario": "loop", "repair_steps": []}
        return super().invoke(role, model, context, timeout)


def benchmark(output: Path, repetitions: int = 1) -> list[dict]:
    if not 1 <= repetitions <= 20:
        raise ValueError("repetitions must be between 1 and 20")
    rows = []
    for repeat in range(repetitions):
        for policy in ("strong-only", "strong-plan-weak", "boundaryloop"):
            with tempfile.TemporaryDirectory(prefix="boundaryloop-benchmark-") as tmp:
                root = Path(tmp)
                cfg = prepare(root)
                task = contract("hard" if policy == "strong-plan-weak" else "easy")
                adapters: dict[str, Adapter] | None = None
                if policy != "boundaryloop":
                    fixture = Baseline(policy == "strong-only")
                    adapters = {"worker": fixture, "architect": fixture}
                    # No escalation in the baseline; stop after its local attempt budget.
                    task = replace(task, escalation_policy={"max_replans": 0})
                    if policy == "strong-only":
                        cfg["worker"]["model"] = "mock-architect"
                started = time.monotonic()
                run = Controller(root, adapters).start(task, cfg)
                expected = "HUMAN_REQUIRED" if policy == "strong-plan-weak" else "COMPLETED"
                if run["state"] != expected:
                    raise BoundaryError(f"Offline policy regression: {policy} ended {run['state']}")
                rows.append(
                    {
                        "policy": policy,
                        "repeat": repeat + 1,
                        "provider": "mock",
                        "worker_model": cfg["worker"]["model"],
                        "architect_model": cfg["architect"]["model"],
                        "verified_success": run["state"] == "COMPLETED",
                        "status": run["state"],
                        "attempts": run["attempts"],
                        "seconds": time.monotonic() - started,
                        "repeated_failure_count": max(
                            0, sum(r["FINAL_STATUS"] == "FAIL" for r in run["receipts"]) - 1
                        ),
                        "strong_interventions": sum(
                            c["role"] == "architect" or (policy == "strong-only")
                            for c in run["calls"]
                        ),
                        "human_interventions": 0,
                        "pending_decisions": len(run["decisions"]),
                        "escalations": len(run["tickets"]),
                        "cost": None,
                        "input_tokens": None,
                        "output_tokens": None,
                        "escalation_precision": None,
                        "false_escalation_rate": None,
                        "missed_escalation_rate": None,
                        "pricing_metadata": "Not applicable: offline fixture, no model calls",
                        "initial_fixture": "port-parser-v1",
                        "validator": "python verify.py",
                    }
                )
    output.mkdir(parents=True, exist_ok=True)
    atomic_write(output / "results.json", json.dumps(rows, indent=2) + "\n")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(output / "results.csv", stream.getvalue())
    report = [
        "# Deterministic orchestration comparison",
        "",
        "Deterministic orchestration tests passed. "
        "Live model performance has not yet been measured.",
        "",
        "This compares fixture-driven policies, not model ability or cost. Baselines use "
        "the same controller's write/verification safeguards, with exception routing disabled.",
        "Costs, token counts and precision metrics are unavailable (null), not zero.",
        "",
        "| Policy | Repeat | Observed result | Attempts |",
        "|---|---:|---|---:|",
    ]
    for row in rows:
        report.append(
            f"| {row['policy']} | {row['repeat']} | {row['status']} | {row['attempts']} |"
        )
    atomic_write(output / "report.md", "\n".join(report) + "\n")
    return rows
