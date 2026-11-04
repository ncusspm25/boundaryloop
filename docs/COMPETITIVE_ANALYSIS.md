# Related work and concrete overlap

Research date: 2026-11-05. These are documentation-based observations, not runtime audits or
competitive benchmarks. Names are ambiguous, so each entry links the exact project reviewed.
No competitor code was incorporated. Lack of a documented feature is not proof of absence.

| Project | Documented behavior | Overlap and demonstrated BoundaryLoop behavior | Not established |
|---|---|---|---|
| [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) | Local multi-agent/model gateway, routing conditions, rewrites, retries/fallbacks, credentials, tools, quotas and usage logs | Both configure models and observe calls. BoundaryLoop's tests demonstrate human-selected difficulty, exact contract/version-bound decisions, immutable verifier execution and checkpoint drift stops. It is a task controller rather than an API gateway. | Whether CCR can reproduce this complete decision lifecycle through extensions; any reliability/cost advantage. |
| [mirabeltech/claude-model-router](https://github.com/mirabeltech/claude-model-router) | Delegate bulk reads to a cheaper worker and report measured avoided work; explicitly independent of Anthropic/Spotify | Cheap bounded work and measurement overlap. BoundaryLoop demonstrates implementation patch gating, deterministic failures, focused tickets and local terminal approvals. | Lower supervision cost or greater safety in production; not benchmarked. |
| [danweinerdev/claude-model-router — model-router](https://github.com/danweinerdev/claude-model-router) | Routing skill, worker agents, hooks and configuration; tiered execution and escalation on verified failure, including plugin specialist registry | Verified escalation substantially overlaps. BoundaryLoop implements an external Python state/decision/write controller and tests rejection, revocation, approval invalidation and drift recovery. | Whether either project handles more real tasks; native hook coverage was not runtime-audited. |
| [junoseong/claude-model-router](https://github.com/junoseong/claude-model-router) | Cost-aware Claude API tier selection using a classifier and refusal-aware execution | Model configuration and escalation are shared concerns. BoundaryLoop requires human initial difficulty and does not automatically classify tasks into model tiers. | Routing quality and costs; no head-to-head test. |
| [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Persistent interrupt/resume, human review and durable graph execution | Human intervention and checkpointed recovery are established capabilities. BoundaryLoop supplies a narrower coding CLI with ready-made contracts, file checks, receipts and local decision confirmation. | HITL or recovery originality; LangGraph can be used to build similar policies. |

BoundaryLoop's demonstrable distinction is the bundled lifecycle: explicit human difficulty →
contract-bound proposals → observed failure limits → focused escalation → scoped human decisions
when needed → checked resumption → independent receipt. The offline tests and demo establish
that this implementation follows those paths. They do not establish a novel research technique,
competitor inferiority, commercial model quality, cost savings, or reduced human attention in
real deployments. Those remain hypotheses requiring comparable live tasks and user studies.
