"""SQLite transactions, integrity checks and an OS-released single-writer lock."""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from .errors import StateError
from .security import actor_id, clean, digest

SCHEMA_VERSION = 1
STATES = {
    "CREATED",
    "PLANNING",
    "READY",
    "RUNNING",
    "VERIFYING",
    "ESCALATION_REQUIRED",
    "DIAGNOSING",
    "HUMAN_REQUIRED",
    "RESUMABLE",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "CANCELLED",
}
TERMINAL = {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}
TRANSITIONS = {
    "CREATED": {"PLANNING", "READY"},
    "PLANNING": {"READY", "HUMAN_REQUIRED"},
    "READY": {"RUNNING"},
    "RUNNING": {"VERIFYING", "ESCALATION_REQUIRED", "HUMAN_REQUIRED"},
    "VERIFYING": {"RUNNING", "READY", "COMPLETED", "ESCALATION_REQUIRED", "HUMAN_REQUIRED"},
    "ESCALATION_REQUIRED": {"DIAGNOSING"},
    "DIAGNOSING": {"RESUMABLE", "HUMAN_REQUIRED"},
    "HUMAN_REQUIRED": {"RESUMABLE"},
    "RESUMABLE": {"READY", "PLANNING", "ESCALATION_REQUIRED"},
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def event(run: dict, kind: str, **details: object) -> None:
    run["events"].append({"timestamp": now(), "kind": kind, **clean(details)})


def transition(run: dict, target: str, reason: str = "") -> None:
    source = run["state"]
    if target == source:
        return
    if target not in STATES or source in TERMINAL:
        raise StateError(f"Invalid state transition {source} -> {target}")
    if target not in {"BLOCKED", "CANCELLED", "FAILED"} | TRANSITIONS.get(source, set()):
        raise StateError(f"Invalid state transition {source} -> {target}")
    if target == "COMPLETED":
        receipts = run.get("receipts", [])
        if (
            not receipts
            or receipts[-1]["FINAL_STATUS"] != "PASS"
            or (receipts[-1]["VALIDATOR_OBSERVED_STATUS"] != "PASS")
            or not receipts[-1]["verification_results"]
            or any(r["status"] != "PASS" for r in receipts[-1]["verification_results"])
        ):
            raise StateError("Completion requires a validator-observed PASS receipt")
    run["state"] = target
    event(run, "state", previous=source, state=target, reason=reason)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.directory = self.root / ".boundaryloop"
        if self.directory.is_symlink() or (
            hasattr(self.directory, "is_junction") and self.directory.is_junction()
        ):
            raise StateError("State directory cannot be a symlink/junction")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.path = self.directory / "state.sqlite3"
        if self.path.is_symlink():
            raise StateError("State database cannot be a symlink")
        try:
            with self.connect() as db:
                db.execute("CREATE TABLE IF NOT EXISTS meta (version INTEGER NOT NULL)")
                if not db.execute("SELECT version FROM meta").fetchall():
                    db.execute("INSERT INTO meta VALUES (?)", (SCHEMA_VERSION,))
                if db.execute("SELECT version FROM meta").fetchall() != [(SCHEMA_VERSION,)]:
                    raise StateError("Unsupported state schema; preserve the database for recovery")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS records "
                    "(kind TEXT, id TEXT, payload TEXT, hash TEXT, PRIMARY KEY(kind,id))"
                )
                if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise StateError("Corrupt state database")
            if os.name != "nt":
                self.path.chmod(0o600)
        except sqlite3.DatabaseError as exc:
            raise StateError(f"Cannot open state database: {exc}") from exc

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=2)
        try:
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        path = self.directory / "writer.lock"
        if path.is_symlink():
            raise StateError("Lock cannot be a symlink")
        with path.open("a+b") as handle:
            handle.seek(0)
            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise StateError("Another controller holds the workspace lock") from exc
            try:
                yield
            finally:
                handle.seek(0)
                if sys.platform == "win32":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def put(self, kind: str, id_: str, value: dict) -> None:
        value = clean(value)
        payload = json.dumps(value, ensure_ascii=True, sort_keys=True)
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO records VALUES (?,?,?,?)",
                    (kind, id_, payload, digest(value)),
                )
        except sqlite3.DatabaseError as exc:
            raise StateError(f"State write failed: {exc}") from exc

    def get(self, kind: str, id_: str) -> dict:
        try:
            with self.connect() as db:
                row = db.execute(
                    "SELECT payload,hash FROM records WHERE kind=? AND id=?",
                    (kind, id_),
                ).fetchone()
            if not row:
                raise StateError(f"Unknown {kind}: {id_}")
            result = json.loads(row[0])
            if digest(result) != row[1]:
                raise StateError(f"State checksum mismatch: {kind}/{id_}")
            if kind == "run" and result.get("state") not in STATES:
                raise StateError("Corrupt run state")
            return result
        except (sqlite3.DatabaseError, json.JSONDecodeError) as exc:
            raise StateError(f"Corrupt state: {exc}") from exc

    def all(self, kind: str) -> list[dict]:
        with self.connect() as db:
            ids = db.execute(
                "SELECT id FROM records WHERE kind=? ORDER BY rowid", (kind,)
            ).fetchall()
        return [self.get(kind, row[0]) for row in ids]

    def clear(self, kind: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM records WHERE kind=?", (kind,))

    def save_run(self, run: dict) -> None:
        if run["owner"] != actor_id():
            raise StateError("Only the local run owner may mutate this run")
        run["updated_at"] = now()
        self.put("run", run["run_id"], run)
