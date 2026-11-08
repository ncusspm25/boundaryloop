"""Install a local wheel in a fresh venv and exercise README commands without network access."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="boundaryloop-clean-install-") as tmp:
        root = Path(tmp)

        def run(argv: list[str]) -> dict | None:
            result = subprocess.run(
                argv,
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(
                    "Installation smoke command failed:\n" + result.stdout + result.stderr
                )
            try:
                return json.loads(result.stdout)
            except ValueError:
                return None

        run([sys.executable, "-m", "venv", str(root / "env")])
        bin_ = root / "env" / ("Scripts" if os.name == "nt" else "bin")
        py = bin_ / ("python.exe" if os.name == "nt" else "python")
        cli = str(bin_ / ("boundaryloop.exe" if os.name == "nt" else "boundaryloop"))
        run([str(py), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
        run([cli, "--help"])
        run([cli, "doctor"])
        run([cli, "demo", "--directory", str(root / "demo")])
        project = root / "quickstart"
        project.mkdir()
        prefix = [cli, "--root", str(project)]
        run([*prefix, "init", "--demo"])
        result = run([*prefix, "start", "--difficulty", "easy", "--task", "Fix the parser bug"])
        if result is None or result.get("state") != "COMPLETED":
            raise RuntimeError("README quickstart did not complete")
        run([*prefix, "status"])
        run([*prefix, "skill", "install"])
        skill = project / ".agents/skills/boundaryloop"
        if not (skill / "SKILL.md").is_file() or list(skill.rglob("*.pyc")):
            raise RuntimeError("Packaged skill missing or bytecode leaked")
        if "allow_implicit_invocation: false" not in (skill / "agents/openai.yaml").read_text(
            encoding="utf-8"
        ):
            raise RuntimeError("Packaged skill must retain its explicit-only invocation policy")
    print("PASS: clean wheel install, help, doctor, demo, README quickstart, packaged Skill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
