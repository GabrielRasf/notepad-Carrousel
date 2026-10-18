"""Uma página: título, subtítulo, texto principal e blocos extras."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from notepad_carrossel.editor.block_editor import BlockEditor
from notepad_carrossel.models import Block, Page

ROLE_LABELS = {
    "title": "TÍTULO",
    "subtitle": "SUBTÍTULO",
    "body": "TEXTO",
    "extra": "BLOCO",
}


class PageView(QWidget):
    content_changed = Signal()
    active_block_changed = Signal(object)
    remove_block_requested = Signal(int)

    def __init__(self, page: Page):
        super().__init__()
        self._page = page
        self._editors: list[BlockEditor] = []
        self.setObjectName("pageView")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.addStretch(1)

        self.card = QFrame()
        self.card.setObjectName("pageCard")
        self.card.setMaximumWidth(780)
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")
        self._form = QVBoxLayout(content)
        self._form.setContentsMargins(36, 28, 36, 36)
        self._form.setSpacing(6)
        for block in page.blocks:
            self._add_editor(block)
        self._form.addStretch(1)
        scroll.setWidget(content)
        card_layout.addWidget(scroll)
        outer.addWidget(self.card, 10)
        outer.addStretch(1)

        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.card.setGraphicsEffect(shadow)

    def pull(self) -> None:
        for editor in self._editors:
            editor.push_to_model()

    def block(self, role: str) -> BlockEditor:
        for editor in self._editors:
            if editor.role == role:
                return editor
        raise KeyError(role)

    def editors(self) -> list[BlockEditor]:
        return list(self._editors)

    def _add_editor(self, block: Block) -> None:
        header = QHBoxLayout()
        header.setContentsMargins(4, 8, 4, 0)
        label = QLabel(ROLE_LABELS.get(block.role, "BLOCO"))
        label.setObjectName("roleLabel")
        header.addWidget(label)
        header.addStretch(1)
        if block.role == "extra" and block.id is not None:
            remove = QPushButton("Remover")
            remove.setObjectName("removeBlock")
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            block_id = block.id
            remove.clicked.connect(lambda _checked=False, ident=block_id: self.remove_block_requested.emit(ident))
            header.addWidget(remove)
        self._form.addLayout(header)

        editor = BlockEditor(block)
        editor.content_changed.connect(self.content_changed)
        editor.focused.connect(self.active_block_changed)
        self._form.addWidget(editor)
        self._editors.append(editor)
