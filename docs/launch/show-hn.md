# Show HN: BoundaryLoop — stop a coding agent after repeated failures and resume with evidence

I built BoundaryLoop to put a small controller around a coding agent's implementation loop.
The problem is specific: planning with a stronger model still leaves the worker making decisions
while implementing. When the same checks keep failing, another patch is not necessarily progress.

You choose Easy or Hard. The worker gets a versioned file-scope contract and immutable verification
commands. After bounded failures the controller preserves a checkpoint and hands the architect
an evidence ticket. Expanding file scope or budgets requires an actual local human confirmation.
Rejection, deferral, revocation and contract invalidation are recorded.

Model routing, hooks and persistent human interrupts already exist elsewhere. This project bundles
that coding-task lifecycle into a dependency-free Python CLI. The offline parser demo uses mock
responses but runs real validators. The Codex CLI adapter sends explicit model ids; the Skill is
guidance, not the controller. It is an experimental release, not a sandbox or a cost-saving claim.

I would value feedback on approval invalidation, crash recovery and whether the decision cards
contain enough evidence to decide without reading the entire log. Please use synthetic reproductions
and review the security boundary before trying it on sensitive repositories.

Repository: https://github.com/ncusspm25/boundaryloop

Maintainer draft; not submitted to Hacker News.
