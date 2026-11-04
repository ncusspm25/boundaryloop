# Recovery

Read `boundaryloop inspect RUN_ID` and `boundaryloop history RUN_ID` before resuming.
The `.boundaryloop/state.sqlite3` database contains versioned contracts, evidence, receipts,
decisions and checkpoint hashes. Preserve it locally; it can contain private code diffs/logs.

Pending decisions remain HUMAN_REQUIRED without input. Interactive approve/reject/defer is bound
to the local OS run owner. Revocation blocks further work without undoing completed changes.
`resume` on a completed run does nothing. Files changed outside the controller cause a stop.
No automatic merge or rollback is attempted. Unknown provider outcomes and interrupted writes
require human reconciliation and a fresh reviewed run. Never run `git reset --hard` for recovery.
