# Security policy

BoundaryLoop 0.1 is experimental. The controller checks proposed file paths, immutable contracts,
verification results and scoped decisions. **It is not an OS sandbox.**

Models are untrusted proposal sources. Repository documents, output and failure memory do not
grant authority. Exact path allowlists reject state, policy, integration and credential paths;
symlinks, junctions, hard-linked edit targets and traversal are rejected. The whole proposal is
checked before writes. Snapshots detect workspace drift before the next edit.

Human-selected verification commands execute with your OS permissions. Generated Python code
executed by a validator can perform side effects. For untrusted repositories or model output,
run the entire tool inside an existing sandbox/container without production credentials.
Native Codex sandboxing is requested read-only; existing hooks, MCP configuration and hosted
tools are outside the controller's complete mediation. Full runtime-enforced mode is unavailable.

Local approval authenticates the current OS account and controlling terminal. It protects the
controller workflow against model files/env flags; it does not defend against a malicious process
already running as the same OS user, a compromised Python installation or an administrator.
SQLite checksums detect accidental corruption, not hostile re-signing by that user. Windows state
inherits the directory's ACL; review it before using a shared directory. POSIX state uses private
directory/file modes. Concurrency protection covers cooperating BoundaryLoop controllers; there
is no claim of race-free mediation against hostile external processes.

`.boundaryloop/` is local/private and ignored by Git. It contains code diffs, validator evidence
and decisions. Pattern-based redaction catches common secrets but cannot recognize every secret.
Do not upload state or raw transcripts. Provider authentication remains in the provider's own
credential storage, never BoundaryLoop config. Scoped context uploads require explicit opt-in.
Terminal control sequences and bidirectional display overrides are stripped from untrusted output.
Telemetry and automatic uploads are absent. Model providers may retain data under their policies.

If you discover an authorization bypass, secret disclosure or recovery defect, do not include
working credentials or private code in a public issue. Use the repository's private vulnerability
reporting feature when enabled. If it is unavailable, open a minimal issue asking for a private
reporting channel without exploit details. Publication must stop for unresolved security defects.

Future reports should include the version, platform, a synthetic reproducer and expected boundary.
