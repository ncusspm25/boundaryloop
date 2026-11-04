"""Content hashes detect drift; checkpoints never reset the user's working tree."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from .errors import SecurityError
from .security import atomic_write, digest, redact, safe_path

EXCLUDED = {
    ".git",
    ".boundaryloop",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "build",
    ".security",
}


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    count = 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.endswith(".egg-info"))
        for name in list(dirs) + sorted(files):
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise SecurityError(f"Workspace contains a symlink/junction: {relative}")
            if path.is_file():
                count += 1
                if count > 20000 or path.stat().st_size > 20 * 1024 * 1024:
                    raise SecurityError(
                        "Workspace exceeds v0.1 snapshot limits (20k files, 20MB/file)"
                    )
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def checkpoint(root: Path, label: str) -> dict:
    files = snapshot(root)
    return {
        "checkpoint_id": uuid.uuid4().hex[:16],
        "label": label,
        "files": files,
        "hash": digest(files),
    }


def assert_unchanged(root: Path, saved: dict) -> None:
    if digest(saved["files"]) != saved["hash"]:
        raise SecurityError("Inconsistent checkpoint hash")
    actual = snapshot(root)
    changed = sorted(
        k for k in set(actual) | set(saved["files"]) if actual.get(k) != saved["files"].get(k)
    )
    if changed:
        raise SecurityError("Workspace differs from checkpoint: " + ", ".join(changed[:12]))


def apply_files(
    root: Path,
    proposed: list[dict],
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
    saved: dict,
) -> list[str]:
    assert_unchanged(root, saved)
    checked = []
    seen = set()
    for change in proposed:
        name = change["path"]
        if name not in allowed or name in forbidden or name.casefold() in seen:
            raise SecurityError(f"Unauthorized or duplicate edit: {name}")
        seen.add(name.casefold())
        path = safe_path(root, name)
        content = change["content"]
        if len(content.encode()) > 512 * 1024:
            raise SecurityError("Proposed file exceeds 512 KiB")
        if redact(content) != content:
            raise SecurityError("Proposed content appears to contain a secret; not writing it")
        checked.append((path, name, content))
    # Validate the entire proposal before applying any part. A crash between files is detected
    # by the pre-write checkpoint journal; recovery stops for reconciliation, never resets.
    for path, _, content in checked:
        atomic_write(path, content)
    return [name for _, name, _ in checked]
