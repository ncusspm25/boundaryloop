"""Path, identity, output and subprocess boundaries. This is not an OS sandbox."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .errors import SecurityError

SECRET_PATTERNS = (
    r"(?:sk|ghp|gho|github_pat|xoxb|xoxp)[-_][A-Za-z0-9_-]{16,}",
    r"(?i)(?:api[_-]?key|password|secret|access[_-]?token)\s*[=:]\s*[^\s,;\"']+",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
)
PRIVATE_NAMES = {".env", ".netrc", ".npmrc", "credentials", "auth.json", "id_rsa", "id_ed25519"}
RESERVED = {
    ".boundaryloop",
    ".git",
    ".agents",
    ".claude",
    ".codex",
    ".github",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".security",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


def redact(text: str) -> str:
    # Untrusted provider/validator text must not issue terminal control or clipboard commands.
    text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", text)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = "".join(
        c
        for c in text
        if (ord(c) >= 32 or c in "\n\t")
        and ord(c) != 127
        and not 0x202A <= ord(c) <= 0x202E
        and not 0x2066 <= ord(c) <= 0x2069
    )
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def clean(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    return value


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def actor_id() -> str:
    """Identity from the OS, never USER/USERNAME or a model-provided actor string."""
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel = ctypes.windll.kernel32
        advapi = ctypes.windll.advapi32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        advapi.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
        token = wintypes.HANDLE()
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
            raise SecurityError("Cannot read the current Windows process token")
        try:
            size = wintypes.DWORD()
            advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
                raise SecurityError("Cannot determine Windows token identity")
            sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
            text = wintypes.LPWSTR()
            if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)):
                raise SecurityError("Cannot resolve Windows SID")
            try:
                return "windows-sid:" + str(text.value)
            finally:
                kernel.LocalFree(ctypes.cast(text, ctypes.c_void_p))
        finally:
            kernel.CloseHandle(token)
    return f"uid:{os.getuid()}"


def relative_name(name: str) -> str:
    if isinstance(name, str) and (
        any(ord(c) < 32 or ord(c) == 127 for c in name)
        or any(0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 for c in name)
    ):
        raise SecurityError("Control/display-override characters are forbidden in paths")
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise SecurityError(f"Invalid relative path: {name!r}")
    p = PurePosixPath(name)
    if p.is_absolute() or PureWindowsPath(name).is_absolute():
        raise SecurityError("Absolute paths are forbidden")
    if any(part in {"", ".", ".."} for part in name.split("/")):
        raise SecurityError("Path traversal or noncanonical path")
    for part in p.parts:
        if part.rstrip(". ") != part or part.casefold() in {"con", "prn", "aux", "nul"}:
            raise SecurityError("Unsafe platform path")
        stem = part.split(".", 1)[0].casefold()
        if stem in {"con", "prn", "aux", "nul"} or re.fullmatch(r"(?:com|lpt)[0-9]", stem):
            raise SecurityError("Reserved Windows device name")
    if any(part.casefold() in RESERVED or part.casefold() in PRIVATE_NAMES for part in p.parts):
        raise SecurityError("Policy, state, credential and integration paths are not worker files")
    if any(part.casefold().startswith(".env") for part in p.parts):
        raise SecurityError("Environment files are private")
    return p.as_posix()


def safe_path(root: Path, name: str) -> Path:
    name = relative_name(name)
    root = root.resolve()
    target = root.joinpath(*name.split("/"))
    for part in [target, *target.parents]:
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise SecurityError(f"Symlink/junction is forbidden: {name}")
    if not target.resolve().is_relative_to(root):
        raise SecurityError("Path escaped repository root")
    if target.is_file() and target.stat().st_nlink > 1:
        raise SecurityError("Hard-linked files cannot be safely replaced")
    return target


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".boundaryloop-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run_process(argv: list[str], cwd: Path, timeout: float, stdin: str | None = None) -> dict:
    """No shell interpolation. Bound runtime and captured output; kill the process tree."""
    if not argv or timeout <= 0:
        raise SecurityError("Empty command or exhausted time budget")
    if any("\x00" in arg for arg in argv):
        raise SecurityError("NUL in command")
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    # Do not propagate this developer's Python package search path into validators.
    env.pop("PYTHONPATH", None)
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                env=env,
                start_new_session=sys.platform != "win32",
                creationflags=creationflags,
            )
        except OSError as exc:
            return {"exit_code": None, "status": "UNAVAILABLE", "output": redact(str(exc))}
        timed_out = False
        try:
            process.communicate(
                input=stdin.encode() if stdin is not None else None, timeout=timeout
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            timed_out = True
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
            process.wait(timeout=10)
            if isinstance(exc, KeyboardInterrupt):
                raise
        stdout.seek(0)
        stderr.seek(0)
        limit = 64 * 1024
        output = stdout.read(limit).decode("utf-8", errors="replace")
        output += stderr.read(limit).decode("utf-8", errors="replace")
        status = "TIMEOUT" if timed_out else ("PASS" if process.returncode == 0 else "FAIL")
        return {"exit_code": process.returncode, "status": status, "output": redact(output)}
