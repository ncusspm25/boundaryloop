"""A real failing Python package fixture, driven by the production controller."""

from __future__ import annotations

import json
from pathlib import Path

from .adapters.mock import BAD
from .config import initialize
from .contracts import Contract
from .errors import BoundaryError
from .orchestrator import Controller
from .security import atomic_write
from .state import Store

VERIFY = """import inspect
import unittest
from parser import parse_port

class PortContract(unittest.TestCase):
    def test_public_api(self):
        self.assertEqual(list(inspect.signature(parse_port).parameters), ["value"])
    def test_valid(self):
        self.assertEqual(parse_port("443"), 443)
        self.assertEqual(parse_port(1), 1)
        self.assertEqual(parse_port(65535), 65535)
    def test_reject_bool(self):
        with self.assertRaises(ValueError):
            parse_port(True)
    def test_range(self):
        for value in (0, -1, 65536):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_port(value)

if __name__ == "__main__":
    unittest.main(verbosity=2)
"""


def contract(difficulty: str = "easy") -> Contract:
    return Contract(
        task_id="port-parser",
        objective="Reject bool and ports outside 1..65535; preserve API",
        difficulty=difficulty,
        contract_version=1,
        approved_scope=("Repair parser.py only; preserve parse_port(value)",),
        allowed_files=("parser.py",),
        forbidden_files=("verify.py", "task-contract.json"),
        allowed_operations=("write",),
        dependencies=(),
        invariants=("Public signature parse_port(value) is unchanged", "Validation is immutable"),
        acceptance_criteria=("verify.py succeeds, including bool, range and signature tests",),
        verification_commands=(("{python}", "verify.py"),),
    )


def prepare(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    names = ("parser.py", "verify.py", "api.py", "task-contract.json", ".boundaryloop")
    if any((root / name).exists() for name in names):
        raise BoundaryError("Demo destination is not fresh; existing files preserved")
    for name, content in {
        "parser.py": BAD,
        "verify.py": VERIFY,
        "api.py": "from parser import parse_port as parse_port\n",
        "task-contract.json": json.dumps(contract().to_dict(), indent=2) + "\n",
    }.items():
        atomic_write(root / name, content)
    Store(root)
    return initialize(root)


def run_demo(root: Path, scenario: str = "repair", difficulty: str = "easy", notify=print) -> dict:
    cfg = prepare(root)
    notify("MOCK DEMO: deterministic fixture responses; real controller and Python verifier")
    notify("Task: reject bool and ports outside 1..65535; preserve parse_port(value)")
    return Controller(root, notify=notify).start(contract(difficulty), cfg, scenario)
