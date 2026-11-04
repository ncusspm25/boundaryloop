from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

from .errors import BoundaryError, SecurityError
from .security import atomic_write, digest, redact

DEFAULT = {
    "schema_version": 1,
    "architect": {"provider": "mock", "model": "mock-architect"},
    "worker": {"provider": "mock", "model": "mock-worker"},
    "validator": {"type": "deterministic", "timeout_seconds": 30},
    "retry_budget": 2,
    "max_replans": 2,
    "max_calls": 12,
    "max_seconds": 600,
    "provider_timeout_seconds": 120,
    "mode": "controlled",
    "telemetry": False,
    "memory": True,
    "learning": False,
    "external_context_authorized": False,
}


def validate(config: dict) -> dict:
    if config.get("schema_version") != 1:
        raise BoundaryError("Unsupported config schema")
    if config.get("mode") == "enforced":
        raise BoundaryError("UNSUPPORTED: full runtime-enforced mode is not available in v0.1")
    if config.get("mode") not in {"controlled", "advisory"}:
        raise BoundaryError("mode must be controlled or advisory")
    for role in ("architect", "worker"):
        value = config.get(role, {})
        if value.get("provider") not in {"mock", "codex", "claude"} or not value.get("model"):
            raise BoundaryError(f"Configure an explicit provider and model for {role}")
    for key in ("max_calls", "max_seconds", "provider_timeout_seconds"):
        if (
            type(config.get(key)) not in (int, float)
            or not math.isfinite(config[key])
            or config[key] <= 0
        ):
            raise BoundaryError(f"{key} must be positive")
    if type(config["max_calls"]) is not int:
        raise BoundaryError("max_calls must be an integer")
    for key, ceiling in (("retry_budget", 10), ("max_replans", 5)):
        if type(config.get(key)) is not int or not 0 <= config[key] <= ceiling:
            raise BoundaryError(f"{key} must be an integer between 0 and {ceiling}")
    for key in ("telemetry", "memory", "learning", "external_context_authorized"):
        if not isinstance(config.get(key), bool):
            raise BoundaryError(f"{key} must be a boolean")
    if config["telemetry"]:
        raise BoundaryError("Telemetry is not implemented; keep it disabled")
    if config.get("validator", {}).get("type") != "deterministic":
        raise BoundaryError("Only deterministic validators are supported")
    if not 0 < config["validator"].get("timeout_seconds", 0) <= 3600:
        raise BoundaryError("Validator timeout must be in (0, 3600]")
    if "max_cost" in config:
        raise BoundaryError("UNSUPPORTED: hard currency caps; use max_calls/time limits instead")
    if redact(json.dumps(config)) != json.dumps(config):
        raise SecurityError("Secrets must not be stored in BoundaryLoop configuration")
    return config


def load(root: Path) -> dict:
    path = root / ".boundaryloop" / "config.json"
    if not path.exists():
        raise BoundaryError("Run boundaryloop init first")
    if path.is_symlink():
        raise SecurityError("Config cannot be a symlink")
    try:
        return validate(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError) as exc:
        raise BoundaryError(f"Invalid configuration: {exc}") from exc


def initialize(root: Path) -> dict:
    path = root / ".boundaryloop" / "config.json"
    if path.exists():
        raise BoundaryError("Already initialized; existing configuration preserved")
    config = deepcopy(DEFAULT)
    atomic_write(path, json.dumps(config, indent=2) + "\n")
    return config


def config_hash(config: dict) -> str:
    return digest(config)
