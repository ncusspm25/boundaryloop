"""Deterministic signals decide retry/escalation; model confidence is unused."""

from __future__ import annotations

import re
from enum import StrEnum

from .security import digest


class Action(StrEnum):
    CONTINUE = "CONTINUE"
    RETRY = "RETRY"
    ESCALATE_STRONG = "ESCALATE_STRONG"
    STRONG_TAKEOVER = "STRONG_TAKEOVER"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    BLOCK = "BLOCK"
    ABORT = "ABORT"


def fingerprint(results: list[dict], area: tuple[str, ...], environment: str = "") -> str:
    normalized = []
    for result in results:
        output = result.get("output", "")
        output = re.sub(r'File "[^"]+", line \d+', "File <path>, line <n>", output)
        output = re.sub(r"\b\d+(?:\.\d+)?s\b|0x[0-9a-fA-F]+", "<n>", output)
        normalized.append(
            {
                "command": result.get("command"),
                "status": result["status"],
                "error": output.strip()[-3000:],
            }
        )
    return digest({"results": normalized, "area": sorted(area), "environment": environment})


def detect(
    *, signal: str, failures: int = 0, retry_budget: int = 2, previous_pass: bool = False
) -> Action:
    if signal in {"unauthorized", "corrupt", "external_change", "loop"}:
        return Action.BLOCK
    if signal in {"human", "budget", "scope"}:
        return Action.REQUEST_HUMAN
    if signal in {"missing_spec", "invariant", "worker_escalation", "unavailable"}:
        return Action.ESCALATE_STRONG
    if signal == "cancel":
        return Action.ABORT
    if signal == "takeover":
        return Action.STRONG_TAKEOVER
    if signal == "pass":
        return Action.CONTINUE
    if previous_pass or failures >= max(1, retry_budget):
        return Action.ESCALATE_STRONG
    return Action.RETRY
