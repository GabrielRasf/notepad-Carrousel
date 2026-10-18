"""Ponto de entrada do Notepad Carrossel."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from notepad_carrossel import __version__
from notepad_carrossel.paths import (
    StorageLayout,
    ensure_layout,
    remember_choice,
    resolve_storage,
)
from notepad_carrossel.ui.main_window import MainWindow
from notepad_carrossel.ui.theme import STYLESHEET, apply_palette


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = _option(args, "--root")
    if "--self-test" in args:
        from notepad_carrossel.selftest import run_self_test

        return run_self_test(Path(root) if root else None)
    if "--smoke-gui" in args:
        return run_smoke(Path(root) if root else None)

    app = _create_app()
    layout = acquire_layout(Path(root) if root else None)
    if layout is None:
        return 1
    return _run_window(app, layout)


def run_smoke(root: Path | None) -> int:
    app = _create_app()
    layout = acquire_layout(root)
    if layout is None:
        return 1
    code = _run_window(app, layout, smoke_ms=800)
    try:
        (layout.data_dir / "smoke-result.txt").write_text("SMOKE_OK\n", encoding="utf-8")
    except OSError:
        return 1
    return 0 if code == 0 else code


def acquire_layout(root: Path | None) -> StorageLayout | None:
    executable = None if root is None else root / "NotepadCarrossel.exe"
    layout, error = resolve_storage(executable=executable)
    if layout is not None:
        ensure_layout(layout)
        return layout

    QMessageBox.warning(
        None,
        "Pasta sem permissão",
        error or "Não foi possível gravar os documentos na pasta do programa.",
    )
    chosen = QFileDialog.getExistingDirectory(None, "Onde guardar os documentos?")
    if not chosen:
        return None
    layout, error = resolve_storage(
        executable=executable,
        preferred_fallback=Path(chosen),
        allow_user_settings=False,
    )
    if layout is None:
        QMessageBox.critical(
            None,
            "Pasta sem permissão",
            error or "A pasta escolhida também não aceita gravação.",
        )
        return None
    try:
        remember_choice(layout.app_dir, layout.root)
    except OSError as exc:
        QMessageBox.warning(
            None,
            "Aviso",
            "A pasta foi aceita, mas não consegui memorizar a escolha junto do programa.\n\n"
            f"{exc}",
        )
    ensure_layout(layout)
    return layout


def _run_window(app: QApplication, layout: StorageLayout, *, smoke_ms: int | None = None) -> int:
    lock = QLockFile(str(layout.data_dir / "instance.lock"))
    lock.setStaleLockTime(15_000)
    if not lock.tryLock(200):
        QMessageBox.warning(None, "Notepad Carrossel", "O Notepad Carrossel já está aberto.")
        return 1
    if smoke_ms is not None:
        QTimer.singleShot(smoke_ms, app.quit)
    try:
        window = MainWindow(layout)
        window.show()
        return int(app.exec())
    finally:
        lock.unlock()


def _create_app() -> QApplication:
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Notepad Carrossel")
    app.setOrganizationName("NotepadCarrossel")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    apply_palette(app)
    app.setStyleSheet(STYLESHEET)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    return app


def _option(args: list[str], name: str) -> str | None:
    if name not in args:
        return None
    index = args.index(name)
    if index + 1 >= len(args):
        raise SystemExit(f"Informe um caminho depois de {name}.")
    return args[index + 1]
