"""Gera uma imagem da janela para conferir o layout. Uso interno."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from notepad_carrossel.paths import ensure_layout, resolve_storage
from notepad_carrossel.ui.main_window import MainWindow
from notepad_carrossel.ui.theme import STYLESHEET, apply_palette


def main() -> int:
    root = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    app = QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    apply_palette(app)
    app.setStyleSheet(STYLESHEET)
    layout, error = resolve_storage(
        executable=root / "NotepadCarrossel.exe",
        allow_user_settings=False,
    )
    if layout is None:
        raise SystemExit(error)
    ensure_layout(layout)
    window = MainWindow(layout)
    window.editor.animations_enabled = False
    window.resize(1280, 800)
    window.show()
    window.new_document("Notas de viagem")
    title = window.editor.block("title")
    title.setPlainText("Lisboa")
    title.apply_alignment("center")
    title.apply_font_size(28)
    title.apply_inline_all("bold", True)
    subtitle = window.editor.block("subtitle")
    subtitle.setPlainText("Três dias a pé")
    subtitle.apply_alignment("left")
    body = window.editor.block("body")
    body.setPlainText(
        "O título fica centralizado, o subtítulo à esquerda e este texto justificado. "
        "A formatação de um bloco não altera os outros."
    )
    body.apply_alignment("justify")
    window.editor.new_page()
    window.editor.block("title").setPlainText("Porto")
    window.editor.go_first()
    app.processEvents()

    def grab() -> None:
        pixmap = window.grab()
        destination.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(destination), "PNG")
        app.quit()

    QTimer.singleShot(400, grab)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
