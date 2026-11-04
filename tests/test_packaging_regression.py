from unittest.mock import patch

from boundaryloop.cli import main


def test_skill_installer_skips_wheel_install_bytecode(tmp_path):
    package = tmp_path / "package"
    skill = package / "skill"
    (skill / "scripts/__pycache__").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: boundaryloop\n---\n", encoding="utf-8")
    (skill / "scripts/status.py").write_text("print('status')\n", encoding="utf-8")
    (skill / "scripts/__pycache__/status.cpython-314.pyc").write_bytes(b"\xa2\xff\x00")
    target = tmp_path / "target"
    target.mkdir()
    with patch("boundaryloop.cli.files", return_value=package):
        assert main(["--root", str(target), "skill", "install"]) == 0
    installed = target / ".agents/skills/boundaryloop"
    assert (installed / "scripts/status.py").exists()
    assert not (installed / "scripts/__pycache__").exists()
