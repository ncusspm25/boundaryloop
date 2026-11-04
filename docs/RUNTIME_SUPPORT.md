# Runtime support and research

Reviewed against official documentation and installed CLI help on 2026-11-05. Integrations must
be rechecked when runtimes change. This file distinguishes product behavior from platform APIs.

| Surface | v0.1 implementation | Boundary |
|---|---|---|
| Codex CLI | real `exec`, explicit model, JSON Schema, read-only sandbox request, JSONL usage | provider availability and runtime sandbox required |
| Native Codex Skill | repo discovery + packaged offline install | procedural/advisory only |
| Native Codex subagents | researched, not used as controller backend | no claim to intercept arbitrary native delegation |
| Codex SDK | researched, not a dependency | no invented Python SDK method |
| App Server | `skills/list` discovery check only | turn/approval orchestration not implemented |
| Claude Code CLI | experimental structured proposal adapter with no built-in tools | native executable required; no live verification yet |
| Full runtime-enforced mode | UNSUPPORTED, fail closed | no comprehensive OS/tool/network mediation |

## Official sources and design choices

[Codex as a platform](https://developers.openai.com/blog/codex-as-a-platform) describes the harness
as an integration surface. BoundaryLoop uses an external deterministic controller, not a claim
that a skill implements permission enforcement.

[Skills](https://developers.openai.com/plugins/build/skills) and
[local skill discovery](https://developers.openai.com/codex/skills) specify YAML-frontmatter
SKILL.md files and repository `.agents/skills` discovery. The packaged installer writes only a
new destination and refuses overwrite. The app-server check verifies discovery without loading
or executing the skill. [Plugin packaging](https://developers.openai.com/plugins/build/plugins)
is a broader distribution option; this release is a skill plus Python package, not a marketplace
plugin or an installed connector.

[AGENTS.md](https://developers.openai.com/codex/guides/agents-md) supplies repository instructions.
It is not a protected state store. Our short file explains conventions; runtime contracts remain
private controller records.

[Subagents](https://developers.openai.com/codex/subagents) support role configuration including
model fields. That does not imply that this session's host exposes arbitrary per-spawn model
selection or approval mediation. BoundaryLoop passes each role's configured model to the real
CLI instead of depending on native delegation.

[Noninteractive Codex](https://developers.openai.com/codex/noninteractive) documents `exec`, JSONL,
output schemas and conversation resume. The PATH launcher's 0.159.2 help was checked; the actual
native transport and discovery check used installed Codex 0.166.0-alpha.5.1. Our adapter
starts an ephemeral, temporary-directory conversation per bounded call. It requests read-only
sandboxing and never-approve; it does not escalate to bypass mode. Process timeout kills the
local process tree; cancellation cannot guarantee a remote provider stopped billing. Existing
user/managed configuration is retained, not silently replaced with looser policy.

[Codex SDK](https://developers.openai.com/codex/sdk) documents a TypeScript thread API and native
resumption. It adds a Node dependency we do not need for proposal transport. BoundaryLoop does
not present its Python API as the official SDK.

[App Server](https://developers.openai.com/codex/app-server) documents initialization, thread/turn
events, `turn/interrupt`, approval callbacks and `skills/list`. These could support deeper future
mediation. This release only implements the discovery diagnostic; it does not invent turn APIs
or claim native handoff/recovery it has not implemented. BoundaryLoop recovery is checkpoint
context in fresh model calls. The diagnostic uses actual JSON-RPC requests and a bounded wait.

[Codex security](https://developers.openai.com/codex/security) separates sandboxing from approval.
BoundaryLoop's exact-path proposal gate is an application control, not a replacement for OS
containment. Trusted validators run under host permissions.

[Hooks](https://developers.openai.com/codex/hooks) document supported lifecycle/tool boundaries,
including PreToolUse, while identifying hosted/specialized tool exceptions. They are insufficient
for a promise to stop arbitrary reasoning or mediate every side effect. BoundaryLoop does not
install global hooks, bypass hook trust or rely on prompts as a permission check.

[Claude programmatic use](https://code.claude.com/docs/en/headless) documents print mode, model
selection, JSON Schema output and tool configuration. Our experimental adapter uses those CLI
flags and reuses the same controller. [Claude hooks](https://code.claude.com/docs/en/hooks) can gate
supported tool events, but are not installed here. Native skills/subagent or hook-based execution
for Claude remains future work, not a completed integration.

[GitHub repository creation](https://cli.github.com/manual/gh_repo_create) supports creating a new
public repository from a clean local source and pushing it. We never reuse an occupied unrelated
repository. [Release creation](https://cli.github.com/manual/gh_release_create) supports explicit
tags, assets and prerelease flags. Authentication, source review, CI and URL verification are
required before reporting publication. General policy reference: [GitHub Docs](https://docs.github.com/).

## Reproduce local diagnostics

```sh
boundaryloop doctor
python scripts/verify_codex_skill.py
python scripts/live_smoke.py --worker YOUR_WORKER_MODEL --architect YOUR_ARCHITECT_MODEL
```

The last command makes real paid/provider calls and transmits only the public parser fixture.
The default test suite never does. See [verification evidence](VERIFICATION.md) for actual results.
