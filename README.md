# BoundaryLoop

Human-governed coding agent orchestration with bounded retries, focused escalation and resumable execution.

A coding agent can spend several patches fixing the same failing test. A better plan alone does
not stop that loop. BoundaryLoop limits the worker's attempts, preserves its work, and hands the
specific failure to an architect model or a human.

```text
$ boundaryloop demo
MOCK DEMO: deterministic fixture responses; real controller and Python verifier
WORKER [mock / mock-worker] implementation
VALIDATOR: FAIL (attempt 1)
RETRY: one bounded repair remains before escalation
WORKER [mock / mock-worker] implementation
VALIDATOR: FAIL (attempt 2)
STOP: ... checkpoint preserved; ticket <id>
ARCHITECT [mock / mock-architect] diagnosis
WORKER [mock / mock-worker] implementation
VALIDATOR: PASS (attempt 3)
```

Install from a source checkout with Python 3.11+: `python -m pip install .`
No runtime dependencies. **v0.1.0 is experimental.** [繁體中文](README.zh-TW.md)

## Demo

```sh
boundaryloop demo --directory demo-repair
boundaryloop demo --directory demo-decision --scenario human
boundaryloop --root demo-decision decisions
```

The fixture fixes a port parser while preserving `parse_port(value)`. Its initial implementation
accepts booleans and out-of-range ports. Two failing attempts create an evidence ticket; the
architect supplies bounded steps; the worker repairs the parser and the Python tests pass.

The second scenario proposes expanding into `api.py`. The controller stops before that edit.
Reject the extension in your own terminal, then resume inside the original contract:

```sh
boundaryloop --root demo-decision decision reject DECISION_ID
# Type the exact confirmation shown in your terminal.
boundaryloop --root demo-decision resume RUN_ID
```

These are **mock model responses through the actual controller**, not live model performance.
The validators and file checks really run. Use a fresh destination for each demo.
[Recording instructions](docs/assets/README.md) · [Architecture](docs/ARCHITECTURE.md)

## Why I built this

The problem this project addresses is the gap between planning and implementation. A worker can
follow a reasonable plan and still reach a decision it cannot resolve. The controller needs to
stop there, preserve evidence, and ask a specific question instead of authorizing another patch.

BoundaryLoop puts that lifecycle in Python rather than relying on a longer agent prompt.
It makes no claim to have invented human-in-the-loop orchestration.
[Related projects and overlap](docs/COMPETITIVE_ANALYSIS.md).

## How it works

- **Easy:** you choose the scope → worker → deterministic verification.
- **Hard:** you choose the scope → architect creates bounded subtasks → worker → verification.
- After two failed local attempts by default, execution stops for an architect diagnosis.
  A repair includes concrete steps and stop conditions. A takeover uses the architect's actual
  configured model for implementation.
- Identical escalations without new code or failure evidence are blocked. Replans and calls are
  bounded too. A worker's completion claim cannot produce a verified result.

Models propose full file contents as structured output. The controller validates the complete
proposal against exact path allowlists before writing anything. It owns contract versions,
checkpoints, retry counts, decisions and execution receipts. It never accepts model-selected
verification commands.

## Human decisions

Local implementation choices stay with the worker. Difficult repairs within scope go to the
architect. File-scope expansion and budget extensions require a human. Neither model can grant
that authority. Ambiguous requirements, security tradeoffs and new interfaces need a new
human-reviewed contract if the existing checks cannot express the change.

```sh
boundaryloop decisions
boundaryloop decision show DECISION_ID
boundaryloop decision approve DECISION_ID --option allow-files
boundaryloop decision reject DECISION_ID
boundaryloop decision defer DECISION_ID
boundaryloop decision revoke DECISION_ID
boundaryloop resume RUN_ID
```

Cards show evidence, attempts, affected files, actual available options, consequences and a safe
default. The queue groups independent cards for reading, sorted by priority; each approval is
confirmed separately. There is no blanket approval switch.

Approvals require the run owner's OS identity, a real interactive terminal, and an exact typed
confirmation. Pipes, environment variables and agent-created files cannot approve a decision.
Approval records bind the task, contract, configuration and checkpoint. Material changes
invalidate them; rejection preserves the original scope. Revocation stops future work without
rolling back files. With no response, the run remains `HUMAN_REQUIRED`.

## Installation

From GitHub:

```sh
git clone https://github.com/ncusspm25/boundaryloop.git
cd boundaryloop
python -m venv .venv
# macOS/Linux: . .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install .
boundaryloop --help
boundaryloop doctor
```

This release is not published to PyPI. Build your own wheel with `python -m build`.
Follow your organization's package and network-install policies.

## Quickstart

For a fresh example directory:

```sh
mkdir parser-work
boundaryloop --root parser-work init --demo
boundaryloop --root parser-work start --difficulty easy --task "Fix the parser bug"
boundaryloop --root parser-work status
```

For your repository, run `boundaryloop init`, create a human-reviewed
`task-contract.json` using [this example](examples/port-parser/task-contract.json), and configure
real providers. Use exact file names and immutable tests; supply verifier argv arrays, not shell
strings. `{python}` resolves to the running interpreter. Every noninteractive start requires
`--difficulty easy` or `--difficulty hard`. Interactive start asks you to choose.

`--root` and `--json` go **before** the command. Exit codes: `0` completed/query, `2` input/error,
`3` human required, `4` blocked, `5` cancelled, `6` failed, `7` unfinished.

## Configuration

The private `.boundaryloop/config.json` starts with mock providers. Select model ids your account
actually supports; BoundaryLoop does not choose a commercially named model for you.

```sh
boundaryloop config set architect.provider codex
boundaryloop config set architect.model YOUR_ARCHITECT_MODEL
boundaryloop config set worker.provider codex
boundaryloop config set worker.model YOUR_WORKER_MODEL
boundaryloop config set external_context_authorized true
boundaryloop start --difficulty hard --contract task-contract.json
```

The final config command authorizes sending the scoped task context to the configured provider.
Cloud execution is not offline or inherently private. The Codex adapter invokes real
`codex exec --model ... --sandbox read-only --output-schema ...`, using existing CLI authentication
and security configuration. It starts fresh bounded conversations with checkpoint context;
BoundaryLoop resume is **not** native Codex conversation resume.

Defaults: two failed local attempts per plan, two strong replans per run, 12 model calls, 600
seconds of active execution, 120 seconds per provider process, 30 seconds per verification
command. Task-contract retry/replan limits govern the run; init copies the configuration defaults
into the demo contract. Elapsed waiting for a human is excluded. Costs remain `null` without
provider billing evidence; this version supports call/time limits, not hard currency caps.

Local failure memory is on; telemetry and adaptive profiles are off. `memory --clear`,
`profile --reset`, and `config set learning false` let you control retained observations.
Profile records show actual verified outcomes and sample counts, not a routing guarantee.

Install the packaged Codex Skill into another repository without a network download:

```sh
boundaryloop --root /path/to/repository skill install
```

Restart Codex to refresh discovery. The repository copy lives in `.agents/skills/boundaryloop/`.
[Runtime capabilities and official sources](docs/RUNTIME_SUPPORT.md).

## What it does not do

- **No full runtime-enforced mode.** Controller file boundaries and approvals are enforced in
  software; native agent tools, MCP, network access and verifier subprocesses are not all mediated.
  `mode=enforced` is rejected. The skill alone is advisory.
- Validators run human-selected commands with host permissions. Use an existing OS/container
  sandbox for untrusted code. Do not give this prerelease production credentials.
- No semantic proof that an arbitrary edit respects a prose requirement. Encode invariants in
  deterministic checks and keep those checks outside worker scope.
- No automatic reset, merge, deployment, deletion, arbitrary model shell command, or approval API
  for unattended automation. Drift and ambiguous crash outcomes stop for reconciliation.
- Claude Code is experimental; its adapter needs a native executable and has not been live-tested.
  There is no dashboard, cloud collaboration or multi-user identity service.

## Benchmarks

```sh
boundaryloop benchmark --repetitions 3
boundaryloop benchmark --report
```

The offline harness isolates the same parser fixture for strong-only, strong-plan/weak-worker,
and BoundaryLoop policies, and writes JSON, CSV and Markdown. Its models are deterministic
fixtures. It demonstrates stopping and recovery, **not** savings or comparative model ability.
Live model performance has not yet been measured in a comparable benchmark. Unavailable token,
cost and escalation-precision measurements are `null`.
[Methodology](benchmarks/README.md) · [Verification record](docs/VERIFICATION.md)

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build --no-isolation
```

The tests use local fixtures; no paid provider is required. Opt-in live smoke and Skill discovery
checks are in `scripts/`. See [CONTRIBUTING.md](CONTRIBUTING.md) for small, real contribution tasks.

## Contributing

Useful feedback includes a reproducible failure, the contract and redacted validator evidence.
Do not post private state databases or raw transcripts. Please read [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
