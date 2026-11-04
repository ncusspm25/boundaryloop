"""Record with your existing terminal capture tool. Responses are MOCK, execution is real."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="boundaryloop-recording-") as tmp:
        root = Path(tmp)
        print("BoundaryLoop — MOCK model demonstration; actual Python verification", flush=True)
        for scenario in ("repair", "human"):
            print(f"\nScenario: {scenario}", flush=True)
            destination = root / scenario
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "boundaryloop",
                    "demo",
                    "--directory",
                    str(destination),
                    "--scenario",
                    scenario,
                ],
                check=False,
            )
            expected = 0 if scenario == "repair" else 3
            if result.returncode != expected:
                return result.returncode or 1
            if scenario == "human":
                subprocess.run(
                    [sys.executable, "-m", "boundaryloop", "--root", str(destination), "decisions"],
                    check=True,
                )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
