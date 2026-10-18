"""Processo auxiliar: grava um documento e, em outra execução, confere os dados."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from notepad_carrossel.paths import ensure_layout, resolve_storage
from notepad_carrossel.ui.main_window import MainWindow


def main() -> None:
    mode = sys.argv[1]
    root = Path(sys.argv[2])
    app = QApplication([])
    layout, error = resolve_storage(
        executable=root / "NotepadCarrossel.exe",
        allow_user_settings=False,
    )
    if layout is None:
        raise SystemExit(error or "sem pasta de dados")
    ensure_layout(layout)
    window = MainWindow(layout)
    window.editor.animations_enabled = False
    if mode == "edit":
        window.new_document("Memória")
        title = window.editor.block("title")
        title.setPlainText("Título central")
        title.apply_alignment("center")
        title.apply_font_size(28)
        title.apply_inline_all("bold", True)
        subtitle = window.editor.block("subtitle")
        subtitle.setPlainText("Subtítulo à esquerda")
        subtitle.apply_alignment("left")
        body = window.editor.block("body")
        body.setPlainText("Texto que permanece — ação")
        body.apply_alignment("justify")
        body.apply_inline_all("italic", True)
        body.apply_font_size(17)
        window.editor.new_page()
        window.editor.block("title").setPlainText("Segunda")
        window.editor.go_first()
        window.save_now()
        window.close()
    elif mode == "read":
        documents = window.db.list_documents()
        if len(documents) != 1:
            raise SystemExit(f"esperava 1 documento, veio {len(documents)}")
        window.open_document(documents[0].id)
        title = window.editor.block("title")
        subtitle = window.editor.block("subtitle")
        body = window.editor.block("body")
        if title.toPlainText() != "Título central":
            raise SystemExit(f"título inesperado: {title.toPlainText()!r}")
        if title.alignment_name() != "center" or title.font_size_value() != 28 or not title.first_char_flags()[0]:
            raise SystemExit("formatação do título perdida")
        if subtitle.alignment_name() != "left" or subtitle.toPlainText() != "Subtítulo à esquerda":
            raise SystemExit("subtítulo perdido")
        if body.toPlainText() != "Texto que permanece — ação":
            raise SystemExit(f"texto inesperado: {body.toPlainText()!r}")
        if body.alignment_name() != "justify" or body.font_size_value() != 17 or not body.first_char_flags()[1]:
            raise SystemExit("formatação do texto principal perdida")
        if body.first_char_flags()[0]:
            raise SystemExit("o negrito do título vazou para o texto")
        window.editor.go_last()
        if window.editor.page_count != 2 or window.editor.block("title").toPlainText() != "Segunda":
            raise SystemExit("a segunda página não sobreviveu")
        window.close()
    else:
        raise SystemExit(f"modo desconhecido: {mode}")
    app.processEvents()
    raise SystemExit(0)


if __name__ == "__main__":
    main()
