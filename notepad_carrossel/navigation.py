"""Regras de navegação do carrossel, independentes da interface."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

_TEXT_INPUTS = (
    QTextEdit,
    QPlainTextEdit,
    QLineEdit,
    QAbstractSpinBox,
    QComboBox,
    QAbstractSlider,
    QAbstractItemView,
)

_TYPING_MODIFIERS = (
    Qt.KeyboardModifier.ShiftModifier
    | Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.MetaModifier
)


def clamp_index(index: int, count: int) -> int:
    if count <= 0:
        return 0
    return max(0, min(count - 1, int(index)))


def step_index(index: int, count: int, delta: int) -> int:
    return clamp_index(index + delta, count)


def index_after_delete(current: int, deleted: int, new_count: int) -> int:
    if new_count <= 0:
        return 0
    if current > deleted:
        current -= 1
    elif current >= new_count:
        current = new_count - 1
    return clamp_index(current, new_count)


def focus_allows_page_arrows(widget: QWidget | None) -> bool:
    """Setas mudam de página somente quando o foco não está em edição de texto."""
    current = widget
    while current is not None:
        if isinstance(current, _TEXT_INPUTS):
            return False
        current = current.parentWidget()
    return True


def page_turn_direction(key: int, modifiers: Qt.KeyboardModifier, focus: QWidget | None) -> int:
    """Retorna -1, +1 ou 0 se a tecla não deve trocar a página.

    Alt+seta navega mesmo com o cursor no editor. Setas simples navegam só
    quando o foco está fora de campos de texto, para não interferir na
    digitação, na seleção ou no movimento do cursor.
    """
    if key == Qt.Key.Key_Left:
        direction = -1
    elif key == Qt.Key.Key_Right:
        direction = 1
    else:
        return 0

    if modifiers & Qt.KeyboardModifier.AltModifier:
        return direction
    if modifiers & _TYPING_MODIFIERS:
        return 0
    if not focus_allows_page_arrows(focus):
        return 0
    return direction
