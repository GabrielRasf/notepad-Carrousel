"""Um bloco de texto com formatação própria."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QPalette,
    QTextCharFormat,
    QTextCursor,
    QTextListFormat,
)
from PySide6.QtWidgets import QTextEdit

from notepad_carrossel.models import ALIGNMENTS, Block
from notepad_carrossel.navigation import page_turn_direction

PLACEHOLDERS = {
    "title": "Título",
    "subtitle": "Subtítulo",
    "body": "Texto principal",
    "extra": "Bloco de texto",
}

MIN_HEIGHT = {
    "title": 72,
    "subtitle": 58,
    "body": 210,
    "extra": 120,
}

ALIGNMENT_QT = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignHCenter,
    "right": Qt.AlignmentFlag.AlignRight,
    "justify": Qt.AlignmentFlag.AlignJustify,
}

LIST_STYLES = {
    "bullet": QTextListFormat.Style.ListDisc,
    "number": QTextListFormat.Style.ListDecimal,
}


def alignment_name_from_qt(alignment: Qt.AlignmentFlag) -> str:
    value = int(alignment)
    if value & int(Qt.AlignmentFlag.AlignJustify):
        return "justify"
    if value & int(Qt.AlignmentFlag.AlignHCenter):
        return "center"
    if value & int(Qt.AlignmentFlag.AlignRight):
        return "right"
    return "left"


class BlockEditor(QTextEdit):
    """Editor rico de um único bloco. A formatação daqui não vaza para os outros."""

    content_changed = Signal()
    focused = Signal(object)

    def __init__(self, block: Block):
        super().__init__()
        self._block = block
        self.role = block.role
        self._alignment = block.alignment if block.alignment in ALIGNMENTS else "left"
        self._font_size = int(block.font_size)
        self._guard = False
        self.setObjectName(f"block_{block.role}")
        self.setAcceptRichText(True)
        self.setTabChangesFocus(True)
        self.setUndoRedoEnabled(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setPlaceholderText(PLACEHOLDERS.get(block.role, "Texto"))
        self._min_height = MIN_HEIGHT.get(block.role, 120)
        self.setMinimumHeight(self._min_height)
        self._apply_paper_palette()
        self.document().setDocumentMargin(4)
        self.document().contentsChanged.connect(self._on_contents_changed)
        self.document().documentLayout().documentSizeChanged.connect(self._fit_height)
        self.set_content(block.html, self._alignment, self._font_size)

    def _apply_paper_palette(self) -> None:
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#fbf7f2"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#1f1a17"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#e7c3b6"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1f1a17"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#b3a89d"))
        self.setPalette(palette)

    def set_content(self, html: str, alignment: str, font_size: int) -> None:
        self._guard = True
        try:
            self._font_size = int(font_size)
            self._alignment = alignment if alignment in ALIGNMENTS else "left"
            self._apply_default_font(self._font_size)
            if html.strip():
                self.setHtml(html)
            else:
                self.clear()
            self._write_font_size(self._font_size)
            self._write_alignment(self._alignment)
        finally:
            self._guard = False
        self._fit_height()

    def push_to_model(self) -> None:
        self._block.html = self.toHtml()
        self._block.alignment = self._alignment
        self._block.font_size = self._font_size

    def alignment_name(self) -> str:
        if self.document().isEmpty() and not self.toPlainText():
            return self._alignment
        detected = alignment_name_from_qt(self.document().firstBlock().blockFormat().alignment())
        return detected or self._alignment

    def font_size_value(self) -> int:
        return int(self._font_size)

    def char_flags_at_cursor(self) -> tuple[bool, bool, bool]:
        fmt = self.currentCharFormat()
        bold = fmt.fontWeight() >= QFont.Weight.DemiBold
        return bold, fmt.fontItalic(), fmt.fontUnderline()

    def first_char_flags(self) -> tuple[bool, bool, bool]:
        cursor = QTextCursor(self.document())
        if self.toPlainText():
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat()
        else:
            fmt = self.currentCharFormat()
        return (
            fmt.fontWeight() >= QFont.Weight.DemiBold,
            fmt.fontItalic(),
            fmt.fontUnderline(),
        )

    def list_kind(self) -> str | None:
        text_list = self.document().firstBlock().textList()
        if text_list is None:
            return None
        style = text_list.format().style()
        if style == QTextListFormat.Style.ListDisc:
            return "bullet"
        if style == QTextListFormat.Style.ListDecimal:
            return "number"
        return "other"

    def apply_alignment(self, name: str) -> None:
        if name not in ALIGNMENT_QT:
            raise ValueError(name)
        self._alignment = name
        self._block.alignment = name
        self._guard = True
        try:
            self._write_alignment(name)
        finally:
            self._guard = False
        self.content_changed.emit()

    def apply_font_size(self, size: int) -> None:
        self._font_size = int(size)
        self._block.font_size = self._font_size
        self._guard = True
        try:
            self._apply_default_font(self._font_size)
            self._write_font_size(self._font_size)
        finally:
            self._guard = False
        self.content_changed.emit()

    def apply_inline(self, kind: str, enabled: bool | None = None) -> None:
        current = self.currentCharFormat()
        fmt = QTextCharFormat()
        if kind == "bold":
            turn_on = (current.fontWeight() < QFont.Weight.DemiBold) if enabled is None else enabled
            fmt.setFontWeight(QFont.Weight.Bold if turn_on else QFont.Weight.Normal)
        elif kind == "italic":
            turn_on = (not current.fontItalic()) if enabled is None else enabled
            fmt.setFontItalic(turn_on)
        elif kind == "underline":
            turn_on = (not current.fontUnderline()) if enabled is None else enabled
            fmt.setFontUnderline(turn_on)
        else:
            raise ValueError(kind)
        self.mergeCurrentCharFormat(fmt)
        self.setFocus()

    def apply_inline_all(self, kind: str, enabled: bool) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)
        self.apply_inline(kind, enabled)
        cursor.endEditBlock()

    def apply_list(self, kind: str) -> None:
        style = LIST_STYLES[kind]
        cursor = self.textCursor()
        cursor.beginEditBlock()
        blocks = self._selected_blocks(cursor)
        first_list = blocks[0].textList()
        already = first_list is not None and first_list.format().style() == style and all(
            item.textList() is first_list for item in blocks
        )
        if already:
            for item in blocks:
                first_list.remove(item)
        else:
            for item in blocks:
                existing = item.textList()
                if existing is not None:
                    existing.remove(item)
            cursor.setPosition(blocks[0].position())
            last = blocks[-1]
            cursor.setPosition(last.position() + max(0, last.length() - 1), QTextCursor.MoveMode.KeepAnchor)
            list_format = QTextListFormat()
            list_format.setStyle(style)
            cursor.createList(list_format)
        cursor.endEditBlock()
        self._write_alignment(self._alignment)
        self.setFocus()

    def focusInEvent(self, event) -> None:  # noqa: N802 - API do Qt
        super().focusInEvent(event)
        self.focused.emit(self)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - API do Qt
        # Alt+seta sobe para a janela. As demais setas continuam no texto.
        if event.modifiers() & Qt.KeyboardModifier.AltModifier and page_turn_direction(
            event.key(), event.modifiers(), self
        ):
            event.ignore()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:  # noqa: N802 - API do Qt
        from PySide6.QtCore import QMimeData

        cleaned = QMimeData()
        if source.hasHtml():
            cleaned.setHtml(source.html())
        if source.hasText():
            cleaned.setText(source.text())
        if not cleaned.hasHtml() and not cleaned.hasText():
            return
        super().insertFromMimeData(cleaned)

    def _on_contents_changed(self) -> None:
        if self._guard:
            return
        self._restore_alignment_if_needed()
        self._fit_height()
        self.content_changed.emit()

    def _restore_alignment_if_needed(self) -> None:
        block = self.document().firstBlock()
        mismatched = False
        while block.isValid():
            if alignment_name_from_qt(block.blockFormat().alignment()) != self._alignment:
                mismatched = True
                break
            block = block.next()
        if not mismatched:
            return
        self._guard = True
        try:
            self._write_alignment(self._alignment)
        finally:
            self._guard = False

    def _fit_height(self, *_args) -> None:
        height = int(self.document().documentLayout().documentSize().height()) + 18
        target = max(self._min_height, min(height, 1400))
        if self.height() != target:
            self.setFixedHeight(target)

    def _apply_default_font(self, size: int) -> None:
        font = QFont("Segoe UI", int(size))
        self.setFont(font)
        self.document().setDefaultFont(font)

    def _write_font_size(self, size: int) -> None:
        cursor = self.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setFontPointSize(int(size))
        cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()
        restored = self.textCursor()
        restored.setPosition(anchor)
        restored.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(restored)

    def _write_alignment(self, name: str) -> None:
        alignment = ALIGNMENT_QT[name]
        cursor = self.textCursor()
        position = cursor.position()
        anchor = cursor.anchor()
        cursor.beginEditBlock()
        block = self.document().firstBlock()
        while block.isValid():
            cursor.setPosition(block.position())
            fmt = cursor.blockFormat()
            fmt.setAlignment(alignment)
            cursor.setBlockFormat(fmt)
            block = block.next()
        cursor.endEditBlock()
        restored = self.textCursor()
        restored.setPosition(anchor)
        restored.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(restored)

    @staticmethod
    def _selected_blocks(cursor: QTextCursor):
        if not cursor.hasSelection():
            return [cursor.block()]
        start = cursor.document().findBlock(cursor.selectionStart())
        end = cursor.document().findBlock(cursor.selectionEnd())
        if cursor.selectionEnd() == end.position() and end != start:
            end = end.previous()
        blocks = []
        current = start
        while current.isValid():
            blocks.append(current)
            if current == end:
                break
            current = current.next()
        return blocks or [cursor.block()]
