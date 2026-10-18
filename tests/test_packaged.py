"""A versão empacotada funciona sem o Python do sistema."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO

EXE = REPO / "dist" / "NotepadCarrossel" / "NotepadCarrossel.exe"


@pytest.mark.skipif(not EXE.is_file(), reason="Executável portátil ainda não foi gerado.")
def test_packaged_executable_roundtrip(tmp_path: Path):
    root = tmp_path / "área portátil" / "Notepad Carrossel"
    root.mkdir(parents=True)
    env = os.environ.copy()
    env["PATH"] = r"C:\Windows\System32"
    env["PYTHONPATH"] = ""
    env.pop("PYTHONHOME", None)
    completed = subprocess.run(
        [str(EXE), "--self-test", "--root", str(root)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    result = root / "data" / "selftest-result.txt"
    details = result.read_text(encoding="utf-8") if result.is_file() else completed.stderr
    assert completed.returncode == 0, details
    assert details.startswith("SELFTEST_OK")
    assert (root / "data" / "notepad.sqlite").is_file()
