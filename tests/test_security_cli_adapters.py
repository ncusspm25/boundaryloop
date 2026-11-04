from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from boundaryloop import checkpoints
from boundaryloop.adapters.base import response, validate_response
from boundaryloop.adapters.codex import CodexAdapter
from boundaryloop.benchmark import benchmark
from boundaryloop.cli import main
from boundaryloop.contracts import Contract
from boundaryloop.demo import contract
from boundaryloop.errors import BoundaryError, ProviderError, SecurityError
from boundaryloop.security import redact, relative_name, run_process, safe_path


@pytest.mark.parametrize(
    "name",
    [
        "../x",
        "/x",
        "C:/x",
        "a/../b",
        "a//b",
        "a\\b",
        ".git/config",
        ".boundaryloop/state.sqlite3",
        ".env",
        "x/.env.production",
        "con",
        "a.",
        "x:stream",
    ],
)
def test_traversal_and_policy_files_rejected(name):
    with pytest.raises(SecurityError):
        relative_name(name)


def test_symlink_and_hardlink_rejected(tmp_path):
    original = tmp_path / "source.py"
    original.write_text("safe")
    linked = tmp_path / "linked.py"
    try:
        linked.hardlink_to(original)
    except OSError:
        pytest.skip("Host does not support hard links")
    with pytest.raises(SecurityError, match="Hard-linked"):
        safe_path(tmp_path, "linked.py")


def test_checkpoint_corruption_and_drift(project):
    root, _ = project
    cp = checkpoints.checkpoint(root, "test")
    cp["files"]["parser.py"] = "invalid"
    with pytest.raises(SecurityError, match="checkpoint hash"):
        checkpoints.assert_unchanged(root, cp)


def test_secret_patch_rejected(project):
    root, _ = project
    cp = checkpoints.checkpoint(root, "test")
    content = "credential = '" + "ghp_" + "X" * 32 + "'"
    with pytest.raises(SecurityError, match="secret"):
        checkpoints.apply_files(
            root, [{"path": "parser.py", "content": content}], ("parser.py",), (), cp
        )


def test_secret_redaction():
    token = "github_pat_" + "X" * 40
    assert token not in redact("message " + token)
    assert "hunter" not in redact("password" + "=" + "hunter")


def test_untrusted_logs_cannot_control_terminal_or_clipboard():
    text = "safe\x1b[31mred\x1b[0m\x1b]52;c;clipboard-data\x07\u202eevil"
    assert redact(text) == "saferedevil"


def test_terminal_controls_cannot_hide_a_secret():
    token = "ghp_" + "X" * 32
    output = token[:4] + "\x1b[31m" + token[4:]
    assert redact(output) == "[REDACTED]"


def test_control_character_path_is_rejected():
    with pytest.raises(SecurityError):
        relative_name("code\x1b[31m.py")


def test_timeout_is_not_pass(tmp_path):
    result = run_process([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, 0.1)
    assert result["status"] == "TIMEOUT"


def test_shell_metacharacters_are_arguments(tmp_path):
    result = run_process(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", "value;echo other"], tmp_path, 10
    )
    assert result["output"].strip() == "value;echo other"


def test_contract_roundtrip_and_no_overlap():
    task = contract()
    assert Contract.from_dict(json.loads(json.dumps(task.to_dict()))).hash == task.hash
    data = task.to_dict()
    data["allowed_files"] = ["verify.py"]
    with pytest.raises(BoundaryError, match="overlap"):
        Contract.from_dict(data)


def test_schema_rejects_hidden_contract_edits():
    value = response("patch", "okay")
    value["new_verification_commands"] = [["echo", "PASS"]]
    with pytest.raises(ProviderError):
        validate_response(value)


def test_codex_uses_real_model_flag_and_readonly_transport(tmp_path):
    captured = []

    def transport(argv, cwd, timeout, stdin=None):
        captured.append((argv, cwd, stdin))
        if "--help" in argv:
            return {"status": "PASS", "output": "--model --sandbox --json --output-schema"}
        output = Path(argv[argv.index("--output-last-message") + 1])
        output.write_text(json.dumps(response("patch", "transport fixture")))
        return {"status": "PASS", "output": ""}

    with (
        patch("boundaryloop.adapters.codex.executable", return_value="codex.exe"),
        patch("boundaryloop.adapters.codex.run_process", side_effect=transport),
    ):
        value = CodexAdapter().invoke("worker", "user-chosen-model", {"contract": {}}, 10)
    argv, cwd, prompt = captured[-1]
    assert argv[argv.index("--model") + 1] == "user-chosen-model"
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[argv.index("-a") + 1] == "never"
    assert cwd != tmp_path and "TASK DATA" in prompt and value["action"] == "patch"


def test_unsupported_codex_cli_rejected(tmp_path):
    with (
        patch("boundaryloop.adapters.codex.executable", return_value="codex.exe"),
        patch(
            "boundaryloop.adapters.codex.run_process",
            return_value={"status": "PASS", "output": "old CLI"},
        ),
    ):
        with pytest.raises(ProviderError, match="configuration"):
            CodexAdapter().invoke("worker", "requested-model", {}, 10)


def test_cli_requires_explicit_noninteractive_difficulty(project, capsys):
    assert main(["--root", str(project[0]), "start"]) == 2
    assert "--difficulty" in capsys.readouterr().err


def test_cli_json_and_exit_status(project, capsys):
    root, _ = project
    assert (
        main(
            [
                "--root",
                str(root),
                "--json",
                "start",
                "--difficulty",
                "easy",
                "--scenario",
                "success",
            ]
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert data["state"] == "COMPLETED"
    assert main(["--root", str(root), "--json", "status"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["state"] == "COMPLETED"


@pytest.mark.parametrize(
    "command",
    [
        "init",
        "doctor",
        "start",
        "status",
        "inspect",
        "resume",
        "cancel",
        "decisions",
        "decision",
        "history",
        "profile",
        "benchmark",
        "config",
        "memory",
        "demo",
        "skill",
    ],
)
def test_cli_help(command):
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0


def test_packaged_skill_installs_without_overwrite(tmp_path):
    destination = tmp_path / ".agents/skills/boundaryloop"
    args = ["--root", str(tmp_path), "skill", "install"]
    assert main(args) == 0
    assert (destination / "SKILL.md").is_file()
    assert main(args) == 2


def test_benchmark_is_isolated_and_has_no_invented_cost(tmp_path):
    rows = benchmark(tmp_path / "report", 1)
    assert len(rows) == 3
    assert all(row["cost"] is None and row["input_tokens"] is None for row in rows)
    assert [r["status"] for r in rows] == ["COMPLETED", "HUMAN_REQUIRED", "COMPLETED"]
    assert (tmp_path / "report/results.csv").is_file()
    assert (
        "Live model performance has not yet been measured"
        in (tmp_path / "report/report.md").read_text()
    )
