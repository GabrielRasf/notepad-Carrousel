"""Barra de formatação aplicada somente ao bloco com foco."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QButtonGroup, QSpinBox, QToolBar, QToolButton

from notepad_carrossel.models import MAX_FONT_SIZE, MIN_FONT_SIZE


class FormatToolbar(QToolBar):
    bold_triggered = Signal()
    italic_triggered = Signal()
    underline_triggered = Signal()
    alignment_triggered = Signal(str)
    font_size_triggered = Signal(int)
    list_triggered = Signal(str)
    add_block_triggered = Signal()

    def __init__(self):
        super().__init__("Formatação")
        self.setMovable(False)
        self.setFloatable(False)
        self.setObjectName("formatToolbar")

        self.bold_button = self._toggle("N", "Negrito", bold=True)
        self.italic_button = self._toggle("I", "Itálico", italic=True)
        self.underline_button = self._toggle("S", "Sublinhado", underline=True)
        self.bold_button.clicked.connect(lambda *_args: self.bold_triggered.emit())
        self.italic_button.clicked.connect(lambda *_args: self.italic_triggered.emit())
        self.underline_button.clicked.connect(lambda *_args: self.underline_triggered.emit())
        self.addWidget(self.bold_button)
        self.addWidget(self.italic_button)
        self.addWidget(self.underline_button)
        self.addSeparator()

        self.size_box = QSpinBox()
        self.size_box.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self.size_box.setSuffix(" pt")
        self.size_box.setToolTip("Tamanho da fonte deste bloco")
        self.size_box.valueChanged.connect(self.font_size_triggered.emit)
        self.addWidget(self.size_box)
        self.addSeparator()

        self._align_group = QButtonGroup(self)
        self._align_group.setExclusive(True)
        self._align_buttons: dict[str, QToolButton] = {}
        for name, label, tip in (
            ("left", "Esq.", "Alinhar o bloco à esquerda"),
            ("center", "Centro", "Centralizar o bloco"),
            ("right", "Dir.", "Alinhar o bloco à direita"),
            ("justify", "Just.", "Justificar o bloco"),
        ):
            button = QToolButton()
            button.setText(label)
            button.setToolTip(tip)
            button.setCheckable(True)
            self._align_group.addButton(button)
            self._align_buttons[name] = button
            self.addWidget(button)
        self._align_buttons["left"].setChecked(True)
        self._align_group.buttonClicked.connect(self._emit_alignment)
        self.addSeparator()

        self.bullet_button = self._toggle("• Lista", "Lista com marcadores")
        self.number_button = self._toggle("1. Lista", "Lista numerada")
        self.bullet_button.clicked.connect(lambda *_args: self.list_triggered.emit("bullet"))
        self.number_button.clicked.connect(lambda *_args: self.list_triggered.emit("number"))
        self.addWidget(self.bullet_button)
        self.addWidget(self.number_button)
        self.addSeparator()

        add_block = QToolButton()
        add_block.setText("Adicionar bloco")
        add_block.setToolTip("Insere um bloco de texto com formatação independente")
        add_block.clicked.connect(lambda *_args: self.add_block_triggered.emit())
        self.addWidget(add_block)
        self.add_block_button = add_block

    def set_inline(self, bold: bool, italic: bool, underline: bool) -> None:
        self._set_checked(self.bold_button, bold)
        self._set_checked(self.italic_button, italic)
        self._set_checked(self.underline_button, underline)

    def set_alignment(self, name: str) -> None:
        button = self._align_buttons.get(name)
        if button is None or button.isChecked():
            return
        self._align_group.blockSignals(True)
        button.setChecked(True)
        self._align_group.blockSignals(False)

    def set_font_size(self, size: int) -> None:
        if self.size_box.value() == int(size):
            return
        self.size_box.blockSignals(True)
        self.size_box.setValue(int(size))
        self.size_box.blockSignals(False)

    def set_list_kind(self, kind: str | None) -> None:
        self._set_checked(self.bullet_button, kind == "bullet")
        self._set_checked(self.number_button, kind == "number")

    def _emit_alignment(self, button) -> None:
        for name, candidate in self._align_buttons.items():
            if candidate is button:
                self.alignment_triggered.emit(name)
                return

    def _toggle(self, text: str, tip: str, *, bold: bool = False, italic: bool = False, underline: bool = False) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tip)
        button.setCheckable(True)
        font = QFont("Segoe UI", 10)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        button.setFont(font)
        return button

    @staticmethod
    def _set_checked(button: QToolButton, checked: bool) -> None:
        if button.isChecked() == checked:
            return
        button.blockSignals(True)
        button.setChecked(checked)
        button.blockSignals(False)
