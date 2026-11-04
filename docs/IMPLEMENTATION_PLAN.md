# v0.1 implementation plan

The release is a Python, standard-library-only controller. Models return structured proposals;
they do not own the contract, verifier or approval store. Exact file allowlists and unchanged
workspace hashes guard controller writes. User-approved argv validators determine completion.

1. Contracts, transactional state, bounded attempts, checkpoints and receipts.
2. OS-identity-bound interactive decisions, immutable versions and invalidation.
3. Deterministic mock and documented Codex CLI structured-output adapter.
4. Failure-injection tests, demo, honest offline comparisons and optional profile.
5. English/Traditional Chinese documentation, packaged/repository skill and launch material.
6. Lint, types, tests, build/install, secret/content review, new public repository and prerelease.

The risk boundary is explicit: validators execute trusted human-selected commands and generated
code with the host user's permissions. The CLI adapter requests Codex read-only sandboxing but
does not promise to mediate every runtime tool/MCP call. Full runtime-enforced mode is rejected
until a supported sandbox/tool mediation implementation is available. No destructive actions,
deployments, provider-created approval files or model-selected shell commands are supported.

The working directory did not contain a Git repository. This project is isolated in a new
`boundaryloop/` child; no sibling material is copied into it. MIT is the initial license.
