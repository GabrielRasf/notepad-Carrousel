"""Reabertura em outro processo e autoteste pela linha de comando."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import REPO


def _child_env(cwd: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(REPO)
    env["QT_API"] = "pyside6"
    return env


def test_restart_in_another_process_keeps_formatting(tmp_path: Path):
    root = tmp_path / "área de trabalho" / "Notepad Carrossel"
    work = tmp_path / "cwd diferente"
    work.mkdir()
    script = REPO / "tests" / "process_roundtrip.py"
    env = _child_env(work)
    edit = subprocess.run(
        [sys.executable, str(script), "edit", str(root)],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert edit.returncode == 0, edit.stderr
    read = subprocess.run(
        [sys.executable, str(script), "read", str(root)],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert read.returncode == 0, read.stderr
    assert (root / "data" / "notepad.sqlite").is_file()


def test_self_test_uses_requested_root_instead_of_cwd(tmp_path: Path):
    root = tmp_path / "pasta com espaço" / "Notepad Carrossel"
    work = tmp_path / "trabalho atual"
    work.mkdir()
    env = _child_env(work)
    completed = subprocess.run(
        [sys.executable, "-m", "notepad_carrossel", "--self-test", "--root", str(root)],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = root / "data" / "selftest-result.txt"
    assert result.read_text(encoding="utf-8").startswith("SELFTEST_OK")
    assert (root / "data" / "notepad.sqlite").is_file()
    assert (root / "backup").is_dir()
    assert not (work / "data").exists()
