# What should happen after a coding agent repeats the same failed fix?

I made a small Python tool, BoundaryLoop, for that point in the workflow. You provide a bounded
contract, exact editable files and verification commands. After two failed local attempts it
stops, preserves the work, and asks an architect model to diagnose the specific failure.

Try `boundaryloop demo` after installing from a checkout. It fixes a parser that accepts booleans
and invalid ports. The responses are deterministic mocks; the file checks, retry limits and Python
tests are real. `boundaryloop demo --scenario human --directory demo-decision` shows a proposed
scope expansion stopping for approval instead of silently editing the API module.

The Codex adapter is real; full runtime sandbox/tool mediation is not implemented, and there is
no measured cost-saving claim. I am looking for technical feedback about false stops and scoped
approval/recovery behavior, not votes.

Before posting: verify community self-promotion rules, tailor this to one relevant community,
and insert the verified repository URL. This draft has not been posted.
