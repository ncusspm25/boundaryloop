An implementation plan does not settle every decision a coding agent encounters.

A failing test may need a local fix. It may also expose an interface conflict, missing requirement,
or a change the agent was never authorized to make. Those cases need different kinds of help.

I built BoundaryLoop as a small Python controller for that distinction. A human chooses the task
difficulty and scope. A worker proposes changes, deterministic tools verify them, and repeated
failures stop at a checkpoint. An architect gets a focused evidence ticket; expanding authority
requires a scoped human decision.

The first experimental release includes a reproducible parser demo, a Codex adapter and tests for
rejection, revocation, drift and interrupted execution. The demo labels mock model responses
explicitly. There is no benchmark claim about cheaper models saving money, and this is not a
replacement for an OS sandbox.

The useful feedback now is concrete: what evidence would you need before approving a scope change,
and which recovery edge case should a coding-agent controller handle first?

Before posting: insert the verified public repository URL. This draft has not been posted.
