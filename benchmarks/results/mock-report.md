# Deterministic orchestration comparison

Deterministic orchestration tests passed. Live model performance has not yet been measured.

This compares fixture-driven policies, not model ability or cost. Baselines use the same controller's write/verification safeguards, with exception routing disabled.
Costs, token counts and precision metrics are unavailable (null), not zero.

| Policy | Repeat | Observed result | Attempts |
|---|---:|---|---:|
| strong-only | 1 | COMPLETED | 1 |
| strong-plan-weak | 1 | HUMAN_REQUIRED | 2 |
| boundaryloop | 1 | COMPLETED | 3 |
| strong-only | 2 | COMPLETED | 1 |
| strong-plan-weak | 2 | HUMAN_REQUIRED | 2 |
| boundaryloop | 2 | COMPLETED | 3 |
| strong-only | 3 | COMPLETED | 1 |
| strong-plan-weak | 3 | HUMAN_REQUIRED | 2 |
| boundaryloop | 3 | COMPLETED | 3 |
