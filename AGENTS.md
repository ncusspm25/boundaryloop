# Repository conventions

Python 3.11+, standard-library runtime, src layout. Keep model adapters separate from the
deterministic controller. Never weaken verification or turn model output into human approval.

Checks: `python -m pytest -q`, `python -m ruff check .`, `python -m ruff format --check .`,
`python -m mypy`, `python -m build --no-isolation`.

Use `.agents/skills/boundaryloop/SKILL.md` when explicitly asked to execute or recover a governed
BoundaryLoop task, not when merely editing the implementation. Fixtures are mock demonstrations,
not model performance measurements. Preserve local state and unrelated changes; no hard resets.
