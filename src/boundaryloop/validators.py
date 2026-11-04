from __future__ import annotations

import sys
import time
from pathlib import Path

from .security import run_process


def verify(
    root: Path, commands: tuple[tuple[str, ...], ...], timeout: float, remaining_seconds: float
) -> list[dict]:
    deadline = time.monotonic() + remaining_seconds
    results = []
    for command in commands:
        argv = [sys.executable if arg == "{python}" else arg for arg in command]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            results.append(
                {
                    "command": list(command),
                    "status": "TIMEOUT",
                    "exit_code": None,
                    "output": "Run time budget exhausted",
                }
            )
            break
        started = time.monotonic()
        result = run_process(argv, root, min(timeout, remaining))
        result.update(command=list(command), seconds=time.monotonic() - started)
        results.append(result)
    return results
