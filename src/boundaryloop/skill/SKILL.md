---
name: boundaryloop
description: Run human-governed coding tasks through the BoundaryLoop CLI, with explicit Easy/Hard routing, bounded retries, independent verification and scoped decisions. Use when the user requests BoundaryLoop execution or recovery; not for ordinary questions or installing dependencies.
---

# BoundaryLoop

This skill is procedural guidance. The installed `boundaryloop` controller enforces proposal
scope, state transitions and verification. The skill itself is not an execution controller.

Inputs: target repository, human-selected `easy` or `hard`, an approved Task Contract, explicit
provider/model configuration and human-selected verification argv. Never infer difficulty.

1. Read repository instructions and run `boundaryloop doctor` and `boundaryloop status`.
2. If not initialized, run `boundaryloop init`. Defaults are offline mock providers.
3. Obtain a machine-readable contract using the fields in
   [contract guidance](references/contracts.md). Scope and validators come from the human;
   model suggestions are not authorization. Do not overwrite existing local policy.
4. Run `boundaryloop start --difficulty easy --contract task-contract.json` (or `hard`).
   To address another repository, put `--root /path/to/repo` before the command.
5. Read the exit code and inspect the run. Only validator-observed `PASS` means verified work.
6. On `HUMAN_REQUIRED`, present `boundaryloop decisions`. Stop dependent actions. Never approve,
   forge actor identity, pipe confirmation, or translate a model suggestion into a human decision.
   The human runs `boundaryloop decision approve ID --option OPTION` in their own terminal.
7. After a recorded decision, use `boundaryloop resume RUN_ID`. Rejections retain the original
   boundary. Do not reintroduce denied actions. Material context changes invalidate approvals.

On provider errors, missing tools, malformed output, corrupt state or checkpoint drift: inspect
the run and explain the exact blocker. Do not delete state, weaken verification, reset Git or
retry an unknown in-flight provider call. `cancel` retains files. See
[recovery](references/recovery.md).

Live providers send scoped task context to their services. Require explicit external-context
authorization. Whole-runtime enforced mode is unsupported in v0.1; never represent read-only
Codex sandbox requests or this skill as comprehensive tool/network mediation.
