"""Ambiente comum dos testes de interface e de armazenamento."""

from __future__ import annotations

import os

os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtGui import QTextDocument

from notepad_carrossel.paths import ensure_layout, resolve_storage
from notepad_carrossel.ui.main_window import MainWindow

REPO = Path(__file__).resolve().parents[1]


def html_to_plain(html: str) -> str:
    document = QTextDocument()
    document.setHtml(html)
    return document.toPlainText()


@pytest.fixture
def storage(tmp_path: Path):
    root = tmp_path / "área de trabalho" / "Notepad Carrossel"
    layout, error = resolve_storage(
        executable=root / "NotepadCarrossel.exe",
        allow_user_settings=False,
    )
    assert layout is not None, error
    ensure_layout(layout)
    return layout


@pytest.fixture
def window(qtbot, storage):
    host = MainWindow(storage)
    host.editor.animations_enabled = False
    host.autosave_delay_ms = 350
    qtbot.addWidget(host)
    host.show()
    qtbot.wait(50)
    return host
