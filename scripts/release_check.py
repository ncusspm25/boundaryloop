"""Bounded source/metadata checks. Heuristic secret checks supplement manual review."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from boundaryloop import __version__
from boundaryloop.security import redact

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise SystemExit("Run this gate in the initialized Git repository after staging source")
    names = [n for n in result.stdout.decode().split("\0") if n]
    if not names:
        raise SystemExit("No staged/tracked source to audit")
    errors = []
    required = {
        "README.md",
        "README.zh-TW.md",
        "LICENSE",
        "SECURITY.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".agents/skills/boundaryloop/SKILL.md",
        "docs/ARCHITECTURE.md",
    }
    errors.extend("Missing required file: " + name for name in required - set(names))
    for name in names:
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            errors.append("Unsafe source path: " + name)
            continue
        if set(path.relative_to(ROOT).parts) & {
            ".venv",
            ".boundaryloop",
            "__pycache__",
            "demo-work",
            ".security",
            "node_modules",
        }:
            errors.append("Private/generated path: " + name)
        if path.suffix in {".sqlite3", ".db", ".pyc", ".pem", ".key", ".cast", ".zip"}:
            errors.append("Unapproved artifact: " + name)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append("Unexpected binary source: " + name)
            continue
        if redact(content) != content:
            errors.append("Potential secret (review manually): " + name)
        if re.search(r"[A-Z]:[\\/](?:Users|AI_dev)[\\/]", content):
            errors.append("Private local absolute path: " + name)
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", content):
                target = target.split("#", 1)[0].split(" ", 1)[0].strip("<>")
                if target and not re.match(r"^[a-z]+:", target):
                    if not (path.parent / unquote(target)).exists():
                        errors.append(f"Broken relative link in {name}: {target}")
    source = ROOT / "src/boundaryloop/skill"
    installed = ROOT / ".agents/skills/boundaryloop"
    for item in source.rglob("*"):
        if item.is_file() and "__pycache__" not in item.parts:
            target = installed / item.relative_to(source)
            if not target.exists() or item.read_bytes() != target.read_bytes():
                errors.append("Skill copies differ: " + str(item.relative_to(source)))
    import tomllib

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())
    if metadata["project"]["version"] != __version__:
        errors.append("Version mismatch")
    if metadata["project"].get("dependencies"):
        errors.append("Review newly introduced runtime dependencies")
    for path in ROOT.glob("examples/**/*.json"):
        json.loads(path.read_text())
    print(
        json.dumps(
            {
                "files_reviewed": len(names),
                "errors": errors,
                "secret_scan": "heuristic; manual staged/history review also required",
            },
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
