# Contract inputs

Required JSON fields: task_id, objective, difficulty, contract_version, approved_scope,
allowed_files, forbidden_files, allowed_operations, dependencies, invariants,
acceptance_criteria, verification_commands, retry_budget, escalation_policy, risk_class.

Use exact repository-relative file names, no globs. Only `write` operations are supported.
List existing tests, verifier scripts, interface baselines and policy files in forbidden_files.
Commands are arrays, for example `[["{python}", "verify.py"]]`; no shell string splitting.
Validators run with the host user's permissions. Use an existing external sandbox for untrusted
code. Invariants written in prose require corresponding deterministic checks to be enforceable.

`boundaryloop init --demo` creates a complete example in a fresh directory. The real project
must have its own requirements and meaningful validators; do not reuse fixture acceptance as
proof of unrelated work.
