"""Immutable, versioned contracts; only the controller creates revisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from .errors import BoundaryError
from .security import digest, relative_name


@dataclass(frozen=True)
class Contract:
    task_id: str
    objective: str
    difficulty: str
    contract_version: int
    approved_scope: tuple[str, ...]
    allowed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    dependencies: tuple[str, ...]
    invariants: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    verification_commands: tuple[tuple[str, ...], ...]
    retry_budget: int = 2
    escalation_policy: dict = field(default_factory=lambda: {"max_replans": 2})
    risk_class: str = "local-code"

    def __post_init__(self) -> None:
        for name in ("task_id", "objective", "difficulty", "risk_class"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise BoundaryError(f"{name} must be a nonempty string")
        for name in (
            "approved_scope",
            "allowed_files",
            "forbidden_files",
            "allowed_operations",
            "dependencies",
            "invariants",
            "acceptance_criteria",
        ):
            if not all(isinstance(value, str) and value for value in getattr(self, name)):
                raise BoundaryError(f"{name} must contain only nonempty strings")
        if type(self.contract_version) is not int or type(self.retry_budget) is not int:
            raise BoundaryError("Contract version and retry budget must be integers")
        if self.difficulty not in {"easy", "hard"}:
            raise BoundaryError("Difficulty must be explicitly easy or hard")
        if not self.task_id or not self.objective or self.contract_version < 1:
            raise BoundaryError("Contract needs an id, objective and positive version")
        if not self.approved_scope or not self.allowed_files:
            raise BoundaryError("Contract needs explicit scope and allowed files")
        if not 0 <= self.retry_budget <= 10:
            raise BoundaryError("retry_budget must be between 0 and 10")
        if not 0 <= self.escalation_policy.get("max_replans", 2) <= 5:
            raise BoundaryError("max_replans must be between 0 and 5")
        if not self.verification_commands or not self.acceptance_criteria:
            raise BoundaryError("Observable acceptance criteria and verification commands required")
        names = [relative_name(n) for n in self.allowed_files + self.forbidden_files]
        if len({n.casefold() for n in self.allowed_files}) != len(self.allowed_files):
            raise BoundaryError("Duplicate or case-colliding allowed paths")
        if {n.casefold() for n in names[: len(self.allowed_files)]} & {
            n.casefold() for n in self.forbidden_files
        }:
            raise BoundaryError("Allowed and forbidden files overlap")
        if set(self.allowed_operations) - {"write"} or "write" not in self.allowed_operations:
            raise BoundaryError(
                "v0.1 supports file writes only, no deletion or model shell commands"
            )
        for command in self.verification_commands:
            if not command or not all(
                isinstance(a, str) and a and "\x00" not in a for a in command
            ):
                raise BoundaryError("Verification commands must be nonempty argv arrays")
            # A directly invoked verifier cannot also be editable, even if omitted from forbidden.
            if {arg.casefold() for arg in command} & {n.casefold() for n in self.allowed_files}:
                raise BoundaryError("A verification command file cannot be an allowed edit target")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def hash(self) -> str:
        return digest(self.to_dict())

    def revision(self, *, steps: list[str], allowed_files: list[str] | None = None) -> Contract:
        return replace(
            self,
            contract_version=self.contract_version + 1,
            approved_scope=self.approved_scope + tuple(steps),
            allowed_files=tuple(allowed_files) if allowed_files is not None else self.allowed_files,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contract:
        data = dict(data)
        for key in (
            "approved_scope",
            "allowed_files",
            "forbidden_files",
            "allowed_operations",
            "dependencies",
            "invariants",
            "acceptance_criteria",
        ):
            if key not in data or not isinstance(data[key], (list, tuple)):
                raise BoundaryError(f"Contract {key} must be an array")
            data[key] = tuple(data[key])
        data["verification_commands"] = tuple(tuple(c) for c in data["verification_commands"])
        try:
            return cls(**data)
        except (TypeError, ValueError) as exc:
            raise BoundaryError(f"Invalid contract: {exc}") from exc
