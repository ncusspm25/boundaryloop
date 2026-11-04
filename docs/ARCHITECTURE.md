# Architecture

Try `boundaryloop demo` first: it executes a failing parser, not a diagram of a future system.

## Components and authority

| Role | Implementation | Authority |
|---|---|---|
| Human Governor | local CLI + `decisions.py` | initial contract, models, scope and budgets |
| Strong Architect | configured adapter, planning/diagnosis phases | bounded plan/repair/takeover proposals |
| Weak Worker | configured adapter, implementation phase | exact-file patch proposals |
| Independent Validator | `validators.py` | execute approved argv, observe exit status/output |
| Boundary Detector | `boundary_detector.py` | deterministic retry/escalation/block signals |
| Decision Controller | `orchestrator.py`, `decisions.py` | finite transitions, no delegated Class C authority |
| State Manager | `state.py`, `checkpoints.py` | transactional records, integrity and drift checks |

Runtime is Python standard library only. CLI parsing is argparse; schemas are Python-validated
JSON plus a JSON Schema for provider output. Frozen contracts serialize all required fields.
The provider cannot change them through its response schema. Hard planning creates subset-file
subcontracts; each inherits the original invariants and full verifier. This deliberately requires
each subtask to leave the acceptance suite passing; tasks needing partial-stage validators must
be split into separately human-reviewed runs in v0.1.

## Execution

Start takes a human-selected difficulty and approved contract. It snapshots repository file
hashes and executes the immutable verification commands for baseline evidence. Easy calls the
worker; Hard first calls the architect for bounded subtasks. A proposal is validated, all paths
checked, and a pre-write journal saved before atomic per-file replacements. Deletion is unsupported.
Verification follows, with source drift detection and a receipt separating worker claim,
validator observation and final result.

Local failed-attempt limits default to two (initial failed implementation plus one repair).
Any previous baseline PASS followed by failure escalates immediately. Worker-reported missing
requirements and unavailable validators also escalate. Call/time exhaustion pauses for a specific
human budget decision. Unauthorized edits block the entire proposal. Retries count all failures
in a plan, a stricter rule than only counting fingerprint-identical failures.

A ticket holds the current contract, unresolved issue, recent failed strategies, bounded diff,
validator output, known facts, open questions and the requested decision. Context includes only
allowed file contents (128 KiB limit), the latest ticket and relevant failure memory. Each response
is structurally validated; repair steps and stopping conditions become an audited revision.
Architecture/requirement changes beyond the human boundary stop for a human-reviewed contract.

Takeover switches the actual implementation call to the architect configuration. Separate model
ids are passed to separate provider invocations. The tool reports provider errors rather than
silently substituting another model. Identical error + code-checkpoint escalation keys block
repetition; a global replan ceiling also prevents routing loops across different failure strings.

## Persistent state and recovery

States: CREATED, PLANNING, READY, RUNNING, VERIFYING, ESCALATION_REQUIRED, DIAGNOSING,
HUMAN_REQUIRED, RESUMABLE, COMPLETED, FAILED, BLOCKED, CANCELLED. Only explicit graph edges and
safe terminal stops are legal. COMPLETED additionally requires observed PASS results.

Schema v1 lives in `.boundaryloop/state.sqlite3`. Each record is JSON with a SHA-256 checksum,
written in a FULL-synchronous SQLite transaction. Contracts, checkpoints, decisions, events,
model assignments, counters and receipts are stored together in a run record. An OS file lock
serializes controller mutations and releases on process death. Queries use SQLite consistency.
Do not copy a live database without SQLite's backup facilities.

Completed resume is idempotent. Pending decisions do not resume. A suspension checkpoint resumes
only if all included file hashes match. External edits, an unknown in-flight provider call or a
partially interrupted write stop for reconciliation. Checkpoints preserve current files and hashes;
they are not automatic rollback archives. Use Git for recoverable source history. No resets,
automatic merges or overwrites of unrelated work occur.

Snapshots omit Git/state, virtualenvs, dependency/build/cache directories. Limits are 20,000
included files and 20 MiB per file. Source outside the snapshot set is not a supported edit target.

## Decisions

Class A is local work inside the contract. Class B is diagnosis and bounded repair inside it.
Class C is new authority: scope, budgets, security/product/interface requirements. Neither model
can approve it. The v0.1 decision vocabulary supports exact file-scope extensions, a fixed budget
increment, rejection, deferral, cancellation and revocation. New requirements/verifiers require a
fresh human-reviewed run. Destructive actions and deployment are never supported operations.

Cards contain only available actions. Queue display batches independent decisions for reading
but never commits a batch approval. OS identity and controlling-terminal confirmation are
checked before recording an action. Binding includes run/task, contract, config and checkpoint.
Authorized progress advances the approval checkpoint; external or material context changes do
not. Replanning after a file-scope grant invalidates it and blocks edits until a fresh review.
Revocation is prospective; it never undoes user files.

## Memory and metrics

Failure keys normalize traceback locations and timings while retaining validator, code area and
environment. They support repeat detection, not proof of common cause. Suggestions are local and
do not bypass verification or permissions. Optional profiles upsert observed attempt outcomes
with model, category, time and sample evidence. No automatic model recommendation is made from
these small samples. Provider token counts are recorded only when emitted; billing costs are null.
See [threat boundaries](../SECURITY.md) and [runtime support](RUNTIME_SUPPORT.md).
