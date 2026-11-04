# Benchmark methodology

`boundaryloop benchmark --repetitions 3` runs three offline fixture policies, each in a fresh
temporary directory with identical parser/verifier bytes. Outputs: `results.json`, `results.csv`,
`report.md`. The machine-readable configuration is [config.json](config.json).

Strong-only uses a fixture successful response. Strong planning + weak implementation plans once
then uses a deliberately unsuccessful worker, with exception routing disabled. BoundaryLoop uses
two failing fixture responses followed by the architect's bounded repair and a passing response.
All use the same controller file and verification safeguards. This is a policy regression harness,
not a claim about how any real strong or weak model behaves. Baseline failure stops at a pending
decision, which is counted separately from an actual human intervention.

Recorded: validator-observed success, active duration, repeated failures, strong invocations,
actual human actions (zero for this unattended fixture), pending decisions and escalations.
Model labels and fixture identity are explicit. Token/currency metrics are null without provider
evidence. Escalation precision, false-escalation and missed-escalation rates are null: this tiny
fixture is not a labeled corpus suitable for those metrics. Never interpret null as zero.

Live comparative benchmarking is not implemented. The opt-in live smoke test validates transport
and a sample task; it cannot establish cost savings or comparative reliability. A future live
benchmark must record model versions, pricing source/date, sandbox environment, fixed initial
Git commit, identical immutable acceptance suites, repeated trials and expected escalation labels.
Keep estimates separate from measured billing, include unsuccessful runs and report uncertainty.
