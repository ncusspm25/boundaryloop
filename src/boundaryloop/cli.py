"""Small, dependency-free terminal interface. JSON goes to stdout; progress to stderr."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from importlib.resources import files
from pathlib import Path

from . import __version__, config, decisions
from .adapters.codex import executable
from .benchmark import benchmark
from .contracts import Contract
from .demo import prepare, run_demo
from .errors import BoundaryError, ProviderError
from .orchestrator import Controller
from .security import atomic_write, clean, run_process
from .state import Store


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="boundaryloop",
        description="Bounded coding-agent execution, verification and scoped human decisions",
    )
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--root", type=Path, default=Path.cwd(), help="Target repository directory")
    p.add_argument(
        "--json", action="store_true", help="Machine-readable output; approvals remain interactive"
    )
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Initialize local private configuration; defaults to mock")
    init.add_argument(
        "--demo", action="store_true", help="Create parser fixture in a fresh directory"
    )
    sub.add_parser("doctor", help="Check local runtime capabilities without invoking a model")
    start = sub.add_parser("start", help="Start an explicitly scoped, verifiable task")
    start.add_argument("--difficulty", choices=("easy", "hard"))
    start.add_argument("--task", help="Objective; otherwise use the contract objective")
    start.add_argument("--contract", type=Path, default=Path("task-contract.json"))
    start.add_argument("--category", default="code-modification")
    start.add_argument(
        "--scenario",
        choices=("repair", "human", "success", "takeover", "loop"),
        default="repair",
        help="Fixture scenario (mock provider only)",
    )
    sub.add_parser("status", help="List run states")
    inspect = sub.add_parser("inspect", help="Inspect contracts, receipts, calls and checkpoints")
    inspect.add_argument("run_id")
    history = sub.add_parser("history", help="Read audit events")
    history.add_argument("run_id", nargs="?")
    for command in ("resume", "cancel"):
        cmd = sub.add_parser(
            command, help=f"{command.capitalize()} a run; never discard local files"
        )
        cmd.add_argument("run_id")
    sub.add_parser("decisions", help="Prioritized pending queue; independent cards shown together")
    decision = sub.add_parser("decision", help="Read or record a scoped local human decision")
    dsub = decision.add_subparsers(dest="action", required=True)
    for action in ("show", "approve", "reject", "defer", "revoke"):
        act = dsub.add_parser(action)
        act.add_argument("decision_id")
        if action == "approve":
            act.add_argument("--option", required=True)
        if action != "show":
            act.add_argument("--reason", default="")
    profile = sub.add_parser("profile", help="Inspect/reset optional verified-outcome samples")
    profile.add_argument("--reset", action="store_true")
    memory = sub.add_parser("memory", help="Inspect/clear local failure fingerprints")
    memory.add_argument("--clear", action="store_true")
    bench = sub.add_parser(
        "benchmark", help="Run isolated mock policy comparisons (not live performance)"
    )
    bench.add_argument("--report", action="store_true")
    bench.add_argument("--output", type=Path, default=Path("benchmark-results"))
    bench.add_argument("--repetitions", type=int, default=1)
    cfg = sub.add_parser("config", help="Read or update local configuration")
    csub = cfg.add_subparsers(dest="action", required=True)
    csub.add_parser("show")
    set_ = csub.add_parser("set")
    set_.add_argument("key", help="Top-level or dotted key, e.g. worker.model")
    set_.add_argument("value", help="JSON literal or string")
    demo = sub.add_parser("demo", help="Run the offline demo with real verifiers")
    demo.add_argument("--directory", type=Path, default=Path("demo-work"))
    demo.add_argument("--scenario", choices=("repair", "human", "takeover"), default="repair")
    demo.add_argument("--difficulty", choices=("easy", "hard"), default="easy")
    skill = sub.add_parser("skill", help="Install the packaged Skill without network access")
    skill.add_argument("action", choices=("install",))
    skill.add_argument(
        "--destination", type=Path, help="Default: current repository .agents/skills/boundaryloop"
    )
    return p


def output(value: object, as_json: bool) -> None:
    if isinstance(value, str) and not as_json:
        print(value)
    else:
        print(json.dumps(clean(value), indent=2, ensure_ascii=True, default=str))


def summary(run: dict) -> dict:
    return {
        key: run.get(key)
        for key in (
            "run_id",
            "task_id",
            "state",
            "attempts",
            "replans",
            "elapsed_seconds",
            "stop_reason",
        )
    }


def doctor(root: Path) -> dict:
    try:
        binary = executable("codex")
        version = run_process([binary, "--version"], root, 10)
        codex = {"available": version["status"] == "PASS", "version": version["output"].strip()}
    except ProviderError as exc:
        codex = {"available": False, "reason": str(exc)}
    return {
        "python": sys.version.split()[0],
        "codex": codex,
        "claude_executable": bool(shutil.which("claude.exe")),
        "controller_file_scope": "enforced at proposal application",
        "full_runtime_enforced_mode": "UNSUPPORTED",
        "validator_sandbox": "Host permissions; use your existing external sandbox",
        "skill_file": (root / ".agents/skills/boundaryloop/SKILL.md").is_file(),
    }


def execute(args: argparse.Namespace) -> tuple[object, int]:
    root = args.root.resolve()
    if not root.is_dir():
        raise BoundaryError("Root must be an existing directory")

    def notify(text: str) -> None:
        print(text, file=sys.stderr)

    if args.command == "doctor":
        return doctor(root), 0
    if args.command == "demo":
        destination = args.directory if args.directory.is_absolute() else root / args.directory
        run = run_demo(destination, args.scenario, args.difficulty, notify=notify)
        if not args.json:
            for decision in run["decisions"]:
                notify(decisions.card(decision))
        return {
            **summary(run),
            "directory": str(destination),
            "mock": True,
        }, exit_code(run)
    if args.command == "benchmark":
        destination = args.output if args.output.is_absolute() else root / args.output
        if args.report:
            return (destination / "report.md").read_text(encoding="utf-8"), 0
        return benchmark(destination, args.repetitions), 0
    if args.command == "skill":
        destination = args.destination or root / ".agents/skills/boundaryloop"
        if destination.exists():
            raise BoundaryError("Skill destination already exists; no overwrite performed")
        source = files("boundaryloop").joinpath("skill")

        def copy(source_, destination_: Path) -> None:
            destination_.mkdir(parents=True)
            for item in source_.iterdir():
                if item.name == "__pycache__" or item.name.endswith((".pyc", ".pyo")):
                    continue
                if item.is_dir():
                    copy(item, destination_ / item.name)
                else:
                    atomic_write(destination_ / item.name, item.read_text(encoding="utf-8"))

        copy(source, destination)
        return {"installed": str(destination), "restart_codex_to_refresh": True}, 0
    if args.command == "init" and args.demo:
        return prepare(root), 0
    store = Store(root)
    if args.command == "init":
        with store.lock():
            return config.initialize(root), 0
    if args.command == "config":
        with store.lock():
            cfg = config.load(root)
            if args.action == "set":
                if any(
                    r["state"] not in {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}
                    for r in store.all("run")
                ):
                    raise BoundaryError(
                        "Cancel or finish the active run before changing configuration"
                    )
                try:
                    value = json.loads(args.value)
                except ValueError:
                    value = args.value
                keys = args.key.split(".")
                target = cfg
                for key in keys[:-1]:
                    if key not in target or not isinstance(target[key], dict):
                        raise BoundaryError("Unknown config key")
                    target = target[key]
                if keys[-1] not in target:
                    raise BoundaryError("Unknown config key")
                target[keys[-1]] = value
                config.validate(cfg)
                atomic_write(store.directory / "config.json", json.dumps(cfg, indent=2) + "\n")
            return cfg, 0
    if args.command == "start":
        difficulty = args.difficulty
        if difficulty is None:
            if not sys.stdin.isatty():
                raise BoundaryError("Noninteractive start requires --difficulty easy|hard")
            difficulty = (
                input("Difficulty [easy: Worker / hard: Architect then Worker]: ").strip().lower()
            )
        path = args.contract if args.contract.is_absolute() else root / args.contract
        data = json.loads(path.read_text(encoding="utf-8"))
        data["difficulty"] = difficulty
        if args.task:
            data["objective"] = args.task
        run = Controller(root, notify=notify).start(
            Contract.from_dict(data), config.load(root), args.scenario, args.category
        )
        if not args.json and run["state"] == "HUMAN_REQUIRED":
            for card in run["decisions"]:
                if card["status"] in {"PENDING", "DEFERRED"}:
                    notify(decisions.card(card))
        return summary(run), exit_code(run)
    if args.command in {"resume", "cancel"}:
        controller = Controller(root, notify=notify)
        run = (
            controller.resume(args.run_id, config.load(root))
            if args.command == "resume"
            else (controller.cancel(args.run_id))
        )
        return summary(run), exit_code(run)
    if args.command == "status":
        return [summary(r) for r in store.all("run")], 0
    if args.command == "inspect":
        return store.get("run", args.run_id), 0
    if args.command == "history":
        runs = [store.get("run", args.run_id)] if args.run_id else store.all("run")
        return [{"run_id": r["run_id"], "events": r["events"]} for r in runs], 0
    if args.command == "decisions":
        pending = [
            d
            for r in store.all("run")
            for d in r["decisions"]
            if d["status"] in {"PENDING", "DEFERRED"}
        ]
        pending.sort(key=lambda d: (d["priority"], d["timestamp"]))
        return pending if args.json else "\n\n".join(decisions.card(d) for d in pending) or (
            "No pending decisions"
        ), 0
    if args.command == "decision":
        if args.action == "show":
            _, value = decisions.find(store, args.decision_id)
        else:
            value = decisions.act(
                store,
                args.decision_id,
                args.action,
                getattr(args, "option", None),
                root,
                args.reason,
            )
        return value if args.json else decisions.card(value), 0
    if args.command in {"memory", "profile"}:
        if getattr(args, "clear", False) or getattr(args, "reset", False):
            with store.lock():
                store.clear(args.command)
        observations = store.all(args.command)
        if args.command == "profile":
            return {
                "sample_count": len(observations),
                "observations": observations,
                "uncertainty": "Descriptive samples; no statistically reliable routing claim",
            }, 0
        return observations, 0
    raise BoundaryError("Unsupported command")


def exit_code(run: dict) -> int:
    return {"COMPLETED": 0, "HUMAN_REQUIRED": 3, "BLOCKED": 4, "CANCELLED": 5, "FAILED": 6}.get(
        run["state"], 7
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value, code = execute(args)
        output(value, args.json)
        return code
    except KeyboardInterrupt:
        print("boundaryloop: interrupted; no decision approved", file=sys.stderr)
        return 130
    except (BoundaryError, OSError, ValueError, KeyError, TypeError) as exc:
        if args.json:
            output({"error": str(exc), "status": "ERROR"}, True)
        else:
            print("boundaryloop: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
