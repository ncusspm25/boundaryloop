"""Experimental Claude Code CLI adapter, using the same proposal semantics."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from ..errors import ProviderError
from ..security import run_process
from .base import SCHEMA
from .codex import INSTRUCTIONS


class ClaudeAdapter:
    def invoke(self, role: str, model: str, context: dict, timeout: float) -> dict:
        binary = shutil.which("claude.exe") or shutil.which("claude")
        if not binary or binary.endswith((".cmd", ".bat", ".ps1")):
            raise ProviderError("Experimental Claude adapter requires a native claude executable")
        with tempfile.TemporaryDirectory(prefix="boundaryloop-claude-") as tmp:
            help_ = run_process([binary, "--help"], Path(tmp), 10)
            if any(flag not in help_["output"] for flag in ("--json-schema", "--tools", "--model")):
                raise ProviderError("Claude runtime lacks required configuration")
            argv = [
                binary,
                "-p",
                "--model",
                model,
                "--tools",
                "",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(SCHEMA),
                "--no-session-persistence",
            ]
            prompt = INSTRUCTIONS.format(role=role) + "\nTASK DATA:\n" + json.dumps(context)
            result = run_process(argv, Path(tmp), timeout, stdin=prompt)
            if result["status"] != "PASS":
                raise ProviderError("Claude invocation failed: " + result["output"][-2000:])
            try:
                envelope = json.loads(result["output"])
                if envelope.get("is_error"):
                    raise ProviderError("Claude returned an error")
                return envelope["structured_output"]
            except (ValueError, KeyError, TypeError) as exc:
                raise ProviderError("Malformed Claude structured output") from exc
