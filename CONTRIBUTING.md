# Contributing

Use Python 3.11 or newer. Install with `python -m pip install -e '.[dev]'` under your local
network-install policy. The runtime has no third-party dependencies.

Before a pull request:

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build --no-isolation
```

Cover changes to permissions, recovery and state transitions with failure-injection tests.
Do not record a provider's claim as a verified outcome. Do not broaden scope to get a test green.
Keep adapters small; the controller owns contract and decision semantics for every provider.
Tests must run offline by default. Live tests need explicit opt-in and model ids.

Please describe the actual trigger, expected result, observed result and the narrowest safe fix.
Redact private paths, source, tokens and model output before attaching evidence.

Real small contribution candidates (not claims that GitHub issues already exist):

- Add shell-completion instructions generated from argparse without runtime dependencies.
- Add a supported macOS terminal confirmation test and document its controlling-terminal behavior.
- Extend traceback normalization for a specific compiler, with false-match regression tests.
- Add an export command for a redacted receipt without exporting the private database.

Discuss changes to authorization, runtime enforcement or schema versions before implementing a
large migration. MIT-licensed contributions should include the origin/license of any reused code.
