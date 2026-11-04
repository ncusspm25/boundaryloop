# Claude Code (experimental)

The optional adapter uses native `claude -p --model ... --tools "" --output-format json
--json-schema ... --no-session-persistence`. It reuses the core contract/decision/receipt semantics.
It requires an existing native executable, supported flags, authentication and explicit external
context authorization. It does not install Claude, change hooks or bypass permissions.

The current Windows npm wrapper is not a tested native transport. No live Claude run is claimed.
Native Skill/Subagent integration, per-tool hook enforcement and session resume remain unsupported.
Codex remains the primary integration. See [runtime sources](../../docs/RUNTIME_SUPPORT.md).
