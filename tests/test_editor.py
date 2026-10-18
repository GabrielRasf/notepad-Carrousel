"""Formatação independente, salvamento automático e reabertura."""

from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox

from notepad_carrossel.storage.database import Database, StorageError
from notepad_carrossel.ui.main_window import MainWindow
from tests.conftest import html_to_plain


def test_blocks_keep_independent_formatting(window):
    window.new_document("Formatos")
    title = window.editor.block("title")
    subtitle = window.editor.block("subtitle")
    body = window.editor.block("body")

    title.setPlainText("Centro")
    title.apply_alignment("center")
    title.apply_font_size(28)
    title.apply_inline_all("bold", True)

    subtitle.setPlainText("Esquerda")
    subtitle.apply_alignment("left")
    subtitle.apply_font_size(16)
    subtitle.apply_inline_all("underline", True)

    body.setPlainText("Justificado")
    body.apply_alignment("justify")
    body.apply_font_size(15)
    body.apply_inline_all("italic", True)

    assert title.alignment_name() == "center"
    assert subtitle.alignment_name() == "left"
    assert body.alignment_name() == "justify"
    assert title.font_size_value() == 28
    assert body.font_size_value() == 15
    assert title.first_char_flags() == (True, False, False)
    assert body.first_char_flags()[0] is False
    assert body.first_char_flags()[1] is True
    assert subtitle.first_char_flags()[2] is True

    window.editor.add_block()
    extra = window.editor.block("extra")
    extra.setPlainText("Nota")
    extra.apply_alignment("right")
    extra.apply_font_size(12)
    assert window.editor.block("title").alignment_name() == "center"
    assert extra.alignment_name() == "right"

    window.save_now()
    assert window.save_indicator_text() == "Salvo"


def test_lists_do_not_spread_to_other_blocks(window, qtbot, storage):
    window.new_document("Listas")
    document_id = window.current_document_id()
    body = window.editor.block("body")
    body.setPlainText("um\ndois")
    cursor = body.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    body.setTextCursor(cursor)
    body.apply_list("number")
    assert body.list_kind() == "number"
    assert window.editor.block("title").list_kind() is None

    subtitle = window.editor.block("subtitle")
    subtitle.setPlainText("item")
    cursor = subtitle.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    subtitle.setTextCursor(cursor)
    subtitle.apply_list("bullet")
    assert subtitle.list_kind() == "bullet"
    assert body.list_kind() == "number"

    window.save_now()
    window.close()

    again = MainWindow(storage)
    again.editor.animations_enabled = False
    qtbot.addWidget(again)
    again.open_document(document_id)
    assert again.editor.block("body").list_kind() == "number"
    assert again.editor.block("subtitle").list_kind() == "bullet"
    assert again.editor.block("title").list_kind() is None
    assert "um" in again.editor.block("body").toPlainText()


def test_autosave_persists_without_clicking_save(window, qtbot, storage):
    window.new_document("Automático")
    document_id = window.current_document_id()
    window.editor.block("body").setPlainText("memória automática")
    assert window.save_indicator_text() == "Salvando"
    qtbot.waitUntil(lambda: window.save_indicator_text() == "Salvo", timeout=3000)

    other = Database(storage.database_path)
    document = other.load_document(document_id)
    assert "memória automática" in html_to_plain(document.pages[0].blocks[2].html)
    other.close()


def test_close_and_reopen_keeps_text_and_format(qtbot, storage):
    host = MainWindow(storage)
    host.editor.animations_enabled = False
    qtbot.addWidget(host)
    host.new_document("Reabrir")
    document_id = host.current_document_id()
    title = host.editor.block("title")
    title.setPlainText("Título central")
    title.apply_alignment("center")
    title.apply_font_size(28)
    title.apply_inline_all("bold", True)
    body = host.editor.block("body")
    body.setPlainText("Texto que permanece")
    body.apply_alignment("justify")
    body.apply_font_size(17)
    host.save_now()
    host.close()

    again = MainWindow(storage)
    again.editor.animations_enabled = False
    qtbot.addWidget(again)
    again.show()
    again.open_document(document_id)
    reloaded_title = again.editor.block("title")
    reloaded_body = again.editor.block("body")
    assert reloaded_title.toPlainText() == "Título central"
    assert reloaded_title.alignment_name() == "center"
    assert reloaded_title.font_size_value() == 28
    assert reloaded_title.first_char_flags()[0] is True
    assert reloaded_body.toPlainText() == "Texto que permanece"
    assert reloaded_body.alignment_name() == "justify"
    assert reloaded_body.font_size_value() == 17
    assert reloaded_body.first_char_flags()[0] is False


def test_save_error_is_visible(window, monkeypatch):
    window.new_document("Erro")
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

    def fail(*args, **kwargs):
        raise StorageError("disco cheio")

    monkeypatch.setattr(window.db, "save_blocks", fail)
    window.editor.block("body").setPlainText("x")
    window.save_now()
    assert window.save_indicator_text() == "Erro ao salvar"
    monkeypatch.undo()
    window.save_now()
    assert window.save_indicator_text() == "Salvo"


def test_backup_restore_export_from_the_window(window, tmp_path):
    window.new_document("Versões")
    window.editor.block("title").setPlainText("versão original")
    window.editor.block("title").apply_alignment("center")
    window.save_now()
    backup = window.backup_now(interactive=False)
    assert backup is not None and backup.is_file()

    window.editor.block("title").setPlainText("versão nova")
    window.save_now()
    destination = tmp_path / "versão exportada.notecarrossel.json"
    exported = window.export_current(destination, interactive=False)
    assert exported == destination

    assert window.restore_from(backup, interactive=False) is True
    document_id = window.db.list_documents()[0].id
    window.open_document(document_id)
    assert window.editor.block("title").toPlainText() == "versão original"
    assert window.editor.block("title").alignment_name() == "center"

    imported = window.import_from(destination, interactive=False)
    assert imported is not None
    assert "versão nova" in window.editor.block("title").toPlainText()


def test_library_lists_recent_document(window):
    window.new_document("Recente")
    window.show_library()
    assert window.library.list.count() == 1
    assert "Recente" in window.library.list.item(0).text()
    assert window.stack.currentWidget() is window.library
