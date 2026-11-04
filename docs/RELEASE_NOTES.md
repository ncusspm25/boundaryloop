# BoundaryLoop v0.1.0 (prerelease)

BoundaryLoop is a Python CLI for human-governed coding agent orchestration. It bounds retries,
preserves failure evidence and checkpoints, and requires scoped local human decisions before
expanding file scope or execution budgets.

## Working in this release

- Explicit Easy/Hard routing, real Codex CLI model configuration and bounded structured proposals.
- Immutable verification commands, execution receipts and focused architect escalation.
- Scoped interactive approve/reject/defer/revoke, invalidation and safe checkpoint resumption.
- Local state/failure memory, optional descriptive profiles and offline policy comparisons.
- Reproducible mock parser demos and an installable/discoverable Codex Skill.

## Install

Download the wheel attached to the verified release, then:

```sh
python -m pip install boundaryloop-0.1.0-py3-none-any.whl
boundaryloop demo
```

Or install from a source checkout with `python -m pip install .`. Python 3.11+ is required.
This version is not published on PyPI. The wheel has no third-party runtime dependencies.

## Experimental and limited

This is not a hardened sandbox. Full runtime tool/network enforcement is unsupported; validators
use host permissions. Native Codex conversation resume is not used: recovery supplies bounded
checkpoint context in fresh calls. Unknown interrupted outcomes require human reconciliation.
Claude Code transport is experimental and not live-tested. Requirements/verifier changes require
a new reviewed run. Live cost/reliability comparisons have not been measured; offline mock results
are not model benchmarks. Read SECURITY.md before using sensitive source or credentials.

Validation evidence is recorded in docs/VERIFICATION.md. See CHANGELOG.md for scope.
