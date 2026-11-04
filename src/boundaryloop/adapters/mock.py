"""Deterministic fixture provider. Never represents live model capability."""

from __future__ import annotations

from .base import response

BAD = "def parse_port(value):\n    return int(value)\n"
REPAIR = (
    "def parse_port(value):\n"
    "    if isinstance(value, bool):\n        raise ValueError('boolean is not a port')\n"
    "    try:\n        port = int(value)\n"
    "    except (TypeError, ValueError) as exc:\n"
    "        raise ValueError('invalid port') from exc\n"
    "    if not 1 <= port <= 65535:\n        raise ValueError('out of range')\n"
    "    return port\n"
)


class MockAdapter:
    def invoke(self, role: str, model: str, context: dict, timeout: float) -> dict:
        scenario = context.get("scenario", "repair")
        contract = context["contract"]
        file = (
            "parser.py"
            if "parser.py" in contract["allowed_files"]
            else contract["allowed_files"][0]
        )
        if role == "architect" and context.get("phase") == "planning":
            return response(
                "plan",
                "One independently validated parser subtask",
                subtasks=[
                    {
                        "objective": contract["objective"],
                        "allowed_files": contract["allowed_files"],
                    },
                ],
            )
        if role == "architect" and context.get("phase") == "diagnosis":
            if scenario == "human" and not context.get("decision_outcome"):
                return response(
                    "human",
                    "Proposed API change needs human authority",
                    diagnosis="The proposed strategy would edit the public API file",
                    steps=["Permit an explicit edit to api.py; keep all validators unchanged"],
                    requested_files=["api.py"],
                )
            if scenario == "takeover":
                return response(
                    "takeover",
                    "Use architect for the next bounded implementation",
                    steps=["Preserve parse_port(value); reject bool and out-of-range ports"],
                    stop_conditions=["Stop if the existing API test fails"],
                )
            return response(
                "repair",
                "Preserve the API; validate boolean and range constraints",
                diagnosis="int() accepts bool and out-of-range integers; both violate the tests",
                steps=["Reject bool before int conversion", "Enforce inclusive range 1..65535"],
                stop_conditions=["Stop if the same verifier fails again"],
            )
        if scenario == "missing_spec":
            return response("escalate", "Missing critical requirement: port range")
        fixed = scenario == "success" or bool(context.get("repair_steps"))
        if scenario == "loop":
            fixed = False
        files = [{"path": file, "content": REPAIR if fixed else BAD}]
        if scenario == "unauthorized":
            files.append({"path": "tests.py", "content": "raise SystemExit(0)\n"})
        return response("patch", "Completed (mock worker claim)", files=files)
