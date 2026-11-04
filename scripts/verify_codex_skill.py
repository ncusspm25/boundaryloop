"""Check real app-server skills/list discovery without starting a model turn."""

from __future__ import annotations

import argparse
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

from boundaryloop.adapters.codex import executable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    process = subprocess.Popen(
        [executable("codex"), "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    inbox: queue.Queue = queue.Queue()

    def read() -> None:
        assert process.stdout
        for line in process.stdout:
            try:
                inbox.put(json.loads(line))
            except ValueError:
                pass

    threading.Thread(target=read, daemon=True).start()

    def send(message: dict) -> None:
        assert process.stdin
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def receive(id_: int) -> dict:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            item = inbox.get(timeout=max(0.01, deadline - time.monotonic()))
            if item.get("id") == id_:
                if "error" in item:
                    raise RuntimeError(str(item["error"]))
                return item["result"]
        raise TimeoutError("Codex app-server response timed out")

    try:
        send(
            {
                "id": 1,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "boundaryloop-discovery-check", "version": "0.1.0"},
                },
            }
        )
        receive(1)
        send({"method": "initialized", "params": {}})
        send(
            {
                "id": 2,
                "method": "skills/list",
                "params": {
                    "cwds": [str(root)],
                    "forceReload": True,
                },
            }
        )
        result = receive(2)
        found = [
            s
            for entry in result.get("data", [])
            for s in entry.get("skills", [])
            if s.get("name") == "boundaryloop"
        ]
        print(
            json.dumps(
                {
                    "discovered": bool(found),
                    "matches": [
                        {"name": s["name"], "enabled": s.get("enabled"), "path": s.get("path")}
                        for s in found
                    ],
                },
                indent=2,
            )
        )
        return 0 if found else 1
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
