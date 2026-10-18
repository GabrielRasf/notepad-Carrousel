"""Navegação do carrossel pelo mouse e pelo teclado."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QTextEdit

from notepad_carrossel.navigation import (
    clamp_index,
    focus_allows_page_arrows,
    index_after_delete,
    page_turn_direction,
    step_index,
)
def test_index_math():
    assert clamp_index(-4, 3) == 0
    assert clamp_index(9, 3) == 2
    assert step_index(0, 4, -1) == 0
    assert step_index(1, 4, 1) == 2
    assert index_after_delete(2, 2, 2) == 1
    assert index_after_delete(0, 0, 2) == 0
    assert index_after_delete(2, 0, 2) == 1


def test_arrow_rules(qtbot):
    editor = QTextEdit()
    field = QLineEdit()
    qtbot.addWidget(editor)
    qtbot.addWidget(field)
    assert focus_allows_page_arrows(None) is True
    assert focus_allows_page_arrows(editor) is False
    assert focus_allows_page_arrows(field) is False
    assert page_turn_direction(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier, editor) == 0
    assert page_turn_direction(Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier, editor) == 0
    assert page_turn_direction(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier, editor) == 0
    assert page_turn_direction(Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier, editor) == 1
    assert page_turn_direction(Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier, editor) == -1
    assert page_turn_direction(Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier, None) == 1
    assert page_turn_direction(Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier, None) == 0


def test_buttons_move_between_pages(window, qtbot):
    window.new_document("Navegação")
    window.editor.block("title").setPlainText("Primeira")
    window.editor.new_page()
    window.editor.block("title").setPlainText("Segunda")
    window.editor.new_page()
    window.editor.block("title").setPlainText("Terceira")
    assert window.editor.indicator_text() == "3 / 3"
    window.editor.go_first()
    assert window.editor.indicator_text() == "1 / 3"
    qtbot.mouseClick(window.editor.btn_next, Qt.MouseButton.LeftButton)
    assert window.editor.indicator_text() == "2 / 3"
    assert window.editor.block("title").toPlainText() == "Segunda"
    qtbot.mouseClick(window.editor.btn_prev, Qt.MouseButton.LeftButton)
    assert window.editor.block("title").toPlainText() == "Primeira"
    window.editor.go_last()
    assert window.editor.indicator_text() == "3 / 3"
    qtbot.mouseClick(window.editor.btn_next, Qt.MouseButton.LeftButton)
    assert window.editor.indicator_text() == "3 / 3"


def test_keyboard_does_not_steal_editing_keys(window, qtbot):
    window.new_document("Digitação")
    window.editor.new_page()
    window.editor.go_first()
    body = window.editor.block("body")
    body.setPlainText("abcd")
    body.setFocus(Qt.FocusReason.OtherFocusReason)
    cursor = body.textCursor()
    cursor.setPosition(1)
    body.setTextCursor(cursor)
    qtbot.keyClick(body, Qt.Key.Key_Right)
    assert window.editor.indicator_text() == "1 / 2"
    assert body.textCursor().position() == 2

    cursor = body.textCursor()
    cursor.setPosition(0)
    body.setTextCursor(cursor)
    qtbot.keyClick(body, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert window.editor.indicator_text() == "1 / 2"
    assert body.textCursor().hasSelection()


def test_alt_and_focus_outside_editor_turn_pages(window, qtbot):
    window.new_document("Atalhos")
    window.editor.new_page()
    window.editor.go_first()
    body = window.editor.block("body")
    body.setPlainText("texto")
    body.setFocus(Qt.FocusReason.OtherFocusReason)
    qtbot.keyClick(body, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    assert window.editor.indicator_text() == "2 / 2"

    window.editor.indicator.setFocus(Qt.FocusReason.OtherFocusReason)
    qtbot.keyClick(window.editor.indicator, Qt.Key.Key_Left)
    assert window.editor.indicator_text() == "1 / 2"


def test_duplicate_insert_and_delete_pages(window, qtbot, monkeypatch):
    window.new_document("Ordem")
    window.editor.block("title").setPlainText("Um")
    window.editor.new_page()
    window.editor.block("title").setPlainText("Dois")
    window.editor.insert_before()
    window.editor.block("title").setPlainText("Meio")
    window.editor.go_first()
    assert window.editor.block("title").toPlainText() == "Um"
    window.editor.step(1)
    assert window.editor.block("title").toPlainText() == "Meio"
    window.editor.step(1)
    assert window.editor.block("title").toPlainText() == "Dois"

    window.editor.go_first()
    window.editor.duplicate_page()
    assert window.editor.page_count == 4
    assert window.editor.block("title").toPlainText() == "Um"
    assert window.editor.current_index == 1

    monkeypatch.setattr(
        "notepad_carrossel.ui.editor_screen.ask_confirmation",
        lambda *args, **kwargs: False,
    )
    assert window.editor.delete_page(interactive=True) is False
    assert window.editor.page_count == 4

    monkeypatch.setattr(
        "notepad_carrossel.ui.editor_screen.ask_confirmation",
        lambda *args, **kwargs: True,
    )
    assert window.editor.delete_page(interactive=True) is True
    assert window.editor.page_count == 3

    only = window.new_document("Única")
    assert only is not None
    assert window.editor.delete_page(interactive=False) is False
    assert window.editor.page_count == 1


def test_fade_transition_does_not_drop_pages(window, qtbot):
    window.editor.animations_enabled = True
    window.new_document("Transição")
    window.editor.block("title").setPlainText("A")
    window.editor.new_page()
    window.editor.block("title").setPlainText("B")
    window.editor.go_first()
    window.editor.step(1)
    qtbot.wait(400)
    assert window.editor.indicator_text() == "2 / 2"
    assert window.editor.block("title").toPlainText() == "B"
    window.editor.step(-1)
    qtbot.wait(400)
    assert window.editor.block("title").toPlainText() == "A"


def test_delete_document_asks_before_removing(window, monkeypatch):
    window.new_document("Temporário")
    document_id = window.current_document_id()
    monkeypatch.setattr(
        "notepad_carrossel.ui.main_window.ask_confirmation",
        lambda *args, **kwargs: False,
    )
    assert window.delete_document(document_id, interactive=True) is False
    assert any(item.id == document_id for item in window.db.list_documents())
    monkeypatch.setattr(
        "notepad_carrossel.ui.main_window.ask_confirmation",
        lambda *args, **kwargs: True,
    )
    assert window.delete_document(document_id, interactive=True) is True
    assert all(item.id != document_id for item in window.db.list_documents())
