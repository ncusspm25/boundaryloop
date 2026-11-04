from __future__ import annotations

from .base import Adapter
from .codex import CodexAdapter
from .mock import MockAdapter


def make_adapter(provider: str) -> Adapter:
    if provider == "mock":
        return MockAdapter()
    if provider == "codex":
        return CodexAdapter()
    if provider == "claude":
        from .claude import ClaudeAdapter

        return ClaudeAdapter()
    raise ValueError(f"Unknown provider: {provider}")
