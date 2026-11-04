from __future__ import annotations

from typing import Any, Protocol

from ..errors import ProviderError

# One deliberately small protocol. Every provider response is validated again in Python.
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": ["patch", "escalate", "repair", "plan", "takeover", "human", "block", "abort"],
        },
        "summary": {"type": "string"},
        "claimed_status": {"type": "string", "enum": ["COMPLETED", "INCOMPLETE", "UNKNOWN"]},
        "diagnosis": {"type": "string"},
        "hypotheses": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "stop_conditions": {"type": "array", "items": {"type": "string"}},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
        "requested_files": {"type": "array", "items": {"type": "string"}},
        "subtasks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "objective": {"type": "string"},
                    "allowed_files": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["objective", "allowed_files"],
            },
        },
    },
    "required": [
        "action",
        "summary",
        "claimed_status",
        "diagnosis",
        "hypotheses",
        "steps",
        "stop_conditions",
        "files",
        "requested_files",
        "subtasks",
    ],
}


def response(action: str, summary: str, **kwargs: object) -> dict:
    value: dict[str, Any] = {
        "action": action,
        "summary": summary,
        "claimed_status": "COMPLETED" if action == "patch" else "UNKNOWN",
        "diagnosis": "",
        "hypotheses": [],
        "steps": [],
        "stop_conditions": [],
        "files": [],
        "requested_files": [],
        "subtasks": [],
    }
    value.update(kwargs)
    return value


def validate_response(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != set(SCHEMA["required"]):
        raise ProviderError("Malformed provider output: unexpected/missing fields")
    if value["action"] not in SCHEMA["properties"]["action"]["enum"]:
        raise ProviderError("Malformed provider action")
    if value["claimed_status"] not in {"COMPLETED", "INCOMPLETE", "UNKNOWN"}:
        raise ProviderError("Malformed claimed status")
    for key in ("summary", "diagnosis"):
        if not isinstance(value[key], str) or len(value[key]) > 16000:
            raise ProviderError(f"Malformed {key}")
    for key in ("steps", "hypotheses", "stop_conditions", "requested_files"):
        if (
            not isinstance(value[key], list)
            or len(value[key]) > 30
            or any(not isinstance(item, str) or len(item) > 8000 for item in value[key])
        ):
            raise ProviderError(f"Malformed {key}")
    for key, fields in (
        ("files", {"path", "content"}),
        ("subtasks", {"objective", "allowed_files"}),
    ):
        if not isinstance(value[key], list) or len(value[key]) > 20:
            raise ProviderError(f"Malformed {key}")
        for item in value[key]:
            if not isinstance(item, dict) or set(item) != fields:
                raise ProviderError(f"Malformed {key} entry")
            if key == "files" and not all(isinstance(item[k], str) for k in fields):
                raise ProviderError("File path/content must be strings")
            if key == "subtasks" and (
                not isinstance(item["objective"], str)
                or not item["objective"]
                or not isinstance(item["allowed_files"], list)
                or not all(isinstance(n, str) for n in item["allowed_files"])
            ):
                raise ProviderError("Malformed subtask")
    return value


class Adapter(Protocol):
    def invoke(self, role: str, model: str, context: dict, timeout: float) -> dict: ...
