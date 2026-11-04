"""Opt-in real provider smoke test. Sends only the public parser fixture to Codex."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from boundaryloop.demo import contract, prepare
from boundaryloop.orchestrator import Controller


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True, help="Model id available to your Codex account")
    parser.add_argument("--architect", required=True)
    parser.add_argument("--difficulty", choices=("easy", "hard"), default="hard")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="boundaryloop-live-") as tmp:
        root = Path(tmp)
        cfg = prepare(root)
        cfg["worker"] = {"provider": "codex", "model": args.worker}
        cfg["architect"] = {"provider": "codex", "model": args.architect}
        cfg["external_context_authorized"] = True
        run = Controller(root, notify=print).start(contract(args.difficulty), cfg)
        report = {
            "state": run["state"],
            "calls": run["calls"],
            "stop_reason": run.get("stop_reason"),
            "attempts": run["attempts"],
            "verified_statuses": [r["FINAL_STATUS"] for r in run["receipts"]],
            "benchmark": False,
        }
        print(json.dumps(report, indent=2))
        return 0 if run["state"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
