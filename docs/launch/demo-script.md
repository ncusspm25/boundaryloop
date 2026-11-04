# Terminal demonstration

Caption throughout: **Mock provider; real BoundaryLoop controller and Python tests**.
Use an existing terminal recorder; no synthetic log animation.

1. 0–5 s: show `boundaryloop demo --directory demo-repair`; explain the parser accepts bool/invalid ports.
2. 5–12 s: two failed validator results. Explain the local attempt budget includes the initial attempt.
3. 12–18 s: highlight STOP, checkpoint and ticket. No third speculative worker call occurs.
4. 18–25 s: show ARCHITECT diagnosis; the missing bool/range constraints become bounded steps.
5. 25–35 s: show worker resumption and actual validator PASS.

These are editing/narration targets, not measured model latencies. The offline run may be faster.

In a separate take:

```sh
boundaryloop demo --directory demo-decision --scenario human
boundaryloop --root demo-decision decisions
boundaryloop --root demo-decision decision reject DECISION_ID
boundaryloop --root demo-decision resume RUN_ID
```

Explain: the proposed API-file expansion was not authorized. Type the real interactive confirmation.
The original allowed-file set remains; the worker repairs within it. Never automate a pretend
human approval or describe mock output as a live model decision. `scripts/record_demo.py` can
capture the two automatic paths; use manual commands to retain the decision workspace.
