# Codex

The production adapter is `src/boundaryloop/adapters/codex.py`; no fake provider API is used.
Configure separate model ids and authorize scoped external context in the private local config.
Repository Skill: `.agents/skills/boundaryloop/SKILL.md`. A wheel includes an identical copy;
`boundaryloop skill install` installs it without downloading or overwriting an existing skill.

`python scripts/verify_codex_skill.py` checks discovery using the documented App Server protocol.
It does not execute skills or start a paid model turn. `python scripts/live_smoke.py --worker ID
--architect ID` is the separate opt-in paid integration test.
See [runtime boundaries](../../docs/RUNTIME_SUPPORT.md).
