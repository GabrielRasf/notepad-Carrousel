"""Página atual, setas do carrossel e controles de páginas."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from notepad_carrossel.editor.block_editor import BlockEditor
from notepad_carrossel.editor.carousel import FadeHost
from notepad_carrossel.editor.page_view import PageView
from notepad_carrossel.models import Document
from notepad_carrossel.navigation import clamp_index, step_index
from notepad_carrossel.storage.backup import BackupManager
from notepad_carrossel.storage.database import Database, StorageError
from notepad_carrossel.ui.dialogs import ask_confirmation
from notepad_carrossel.ui.format_toolbar import FormatToolbar


class EditorScreen(QWidget):
    content_changed = Signal()
    structure_changed = Signal()
    index_changed = Signal(int)

    def __init__(self, database: Database, backups: BackupManager):
        super().__init__()
        self.db = database
        self.backups = backups
        self.animations_enabled = True
        self._doc: Document | None = None
        self._index = 0
        self._view: PageView | None = None
        self._active: BlockEditor | None = None
        self._dirty = False

        self.toolbar = FormatToolbar()
        self.toolbar.bold_triggered.connect(lambda: self._apply(lambda block: block.apply_inline("bold")))
        self.toolbar.italic_triggered.connect(lambda: self._apply(lambda block: block.apply_inline("italic")))
        self.toolbar.underline_triggered.connect(lambda: self._apply(lambda block: block.apply_inline("underline")))
        self.toolbar.alignment_triggered.connect(lambda name: self._apply(lambda block: block.apply_alignment(name)))
        self.toolbar.font_size_triggered.connect(lambda size: self._apply(lambda block: block.apply_font_size(size)))
        self.toolbar.list_triggered.connect(lambda kind: self._apply(lambda block: block.apply_list(kind)))
        self.toolbar.add_block_triggered.connect(lambda *_args: self.add_block())

        self.btn_prev = self._arrow("‹", "Página anterior")
        self.btn_next = self._arrow("›", "Próxima página")
        self.btn_prev.setObjectName("arrowButton")
        self.btn_next.setObjectName("arrowButton")
        self.btn_prev.clicked.connect(lambda *_args: self.step(-1))
        self.btn_next.clicked.connect(lambda *_args: self.step(1))
        self.host = FadeHost()

        stage = QHBoxLayout()
        stage.setContentsMargins(12, 8, 12, 0)
        stage.setSpacing(8)
        stage.addWidget(self.btn_prev, 0, Qt.AlignmentFlag.AlignVCenter)
        stage.addWidget(self.host, 1)
        stage.addWidget(self.btn_next, 0, Qt.AlignmentFlag.AlignVCenter)

        self.indicator = QLabel("0 / 0")
        self.indicator.setObjectName("pageIndicator")
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicator.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.indicator.setToolTip(
            "Clique aqui e use as setas para mudar de página. "
            "Durante a digitação, use Alt + setas."
        )

        self.btn_first = self._button("Primeira", "Ir para a primeira página")
        self.btn_last = self._button("Última", "Ir para a última página")
        self.btn_new_page = self._button("Nova página", "Criar uma página no fim do documento")
        self.btn_duplicate = self._button("Duplicar", "Duplicar a página atual")
        self.btn_insert_before = self._button("Inserir antes", "Inserir uma página antes da atual")
        self.btn_insert_after = self._button("Inserir depois", "Inserir uma página depois da atual")
        self.btn_delete_page = self._button("Excluir página", "Excluir a página atual")
        self.btn_delete_page.setObjectName("danger")
        self.btn_first.clicked.connect(lambda *_args: self.go_first())
        self.btn_last.clicked.connect(lambda *_args: self.go_last())
        self.btn_new_page.clicked.connect(lambda *_args: self.new_page())
        self.btn_duplicate.clicked.connect(lambda *_args: self.duplicate_page())
        self.btn_insert_before.clicked.connect(lambda *_args: self.insert_before())
        self.btn_insert_after.clicked.connect(lambda *_args: self.insert_after())
        self.btn_delete_page.clicked.connect(lambda *_args: self.delete_page(interactive=True))

        controls = QHBoxLayout()
        controls.setContentsMargins(16, 8, 16, 4)
        controls.setSpacing(8)
        controls.addWidget(self.btn_first)
        controls.addWidget(self.indicator)
        controls.addWidget(self.btn_last)
        controls.addStretch(1)
        controls.addWidget(self.btn_new_page)
        controls.addWidget(self.btn_duplicate)
        controls.addWidget(self.btn_insert_before)
        controls.addWidget(self.btn_insert_after)
        controls.addWidget(self.btn_delete_page)

        hint = QLabel("As setas do teclado mudam de página fora do texto. Durante a digitação, use Alt + setas.")
        hint.setObjectName("hintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)
        layout.addWidget(self.toolbar)
        layout.addLayout(stage, 1)
        layout.addLayout(controls)
        layout.addWidget(hint)

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def has_document(self) -> bool:
        return self._doc is not None and self._doc.id is not None

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def page_count(self) -> int:
        if self._doc is None:
            return 0
        return len(self._doc.pages)

    def indicator_text(self) -> str:
        return self.indicator.text()

    def block(self, role: str) -> BlockEditor:
        if self._view is None:
            raise RuntimeError("Nenhuma página está aberta.")
        return self._view.block(role)

    def load(self, document: Document) -> None:
        self._doc = document
        self._index = clamp_index(document.current_page_index, len(document.pages))
        self._dirty = False
        self._view = None
        self._active = None
        self._render(animated=False)
        self._update_controls()

    def unload(self) -> None:
        self._doc = None
        self._view = None
        self._active = None
        self._dirty = False
        blank = QWidget()
        self.host.show_widget(blank, animated=False)
        self._update_controls()

    def save_current(self, *, touch: bool) -> None:
        if self._doc is None or self._doc.id is None or self._view is None or not self.db.is_open:
            return
        self._view.pull()
        self.db.save_blocks(self._doc.id, self._doc.pages[self._index].blocks, touch=touch)
        self.db.set_current_page(self._doc.id, self._index)
        self._dirty = False

    def step(self, direction: int) -> None:
        if self._doc is None:
            return
        self.go_to(step_index(self._index, len(self._doc.pages), direction))

    def go_to(self, index: int) -> None:
        if self._doc is None:
            return
        target = clamp_index(index, len(self._doc.pages))
        if self._view is not None and target == self._index:
            self._update_controls()
            return
        if self._view is not None:
            self.save_current(touch=self._dirty)
        self._index = target
        self._doc.current_page_index = target
        if self._doc.id is not None and self.db.is_open:
            self.db.set_current_page(self._doc.id, target)
        self._render(animated=self.animations_enabled)
        self.index_changed.emit(target)
        self._update_controls()

    def go_first(self) -> None:
        self.go_to(0)

    def go_last(self) -> None:
        self.go_to(max(0, self.page_count - 1))

    def new_page(self) -> None:
        self._insert_at(self.page_count)

    def insert_before(self) -> None:
        self._insert_at(self._index)

    def insert_after(self) -> None:
        self._insert_at(self._index + 1)

    def duplicate_page(self) -> None:
        if not self.has_document:
            return
        self.save_current(touch=True)
        new_index = self.db.duplicate_page(self._doc.id, self._index)
        self._reload(new_index)

    def delete_page(self, *, interactive: bool = True) -> bool:
        if not self.has_document or self._doc is None or self._doc.id is None:
            return False
        if self.page_count <= 1:
            if interactive:
                QMessageBox.information(
                    self,
                    "Excluir página",
                    "O documento precisa ter ao menos uma página.",
                )
            return False
        if interactive and not ask_confirmation(
            self,
            "Excluir página",
            f"Excluir a página {self._index + 1} de {self.page_count}?\n\n"
            "Uma cópia de segurança será criada antes da exclusão.",
            accept="Excluir",
        ):
            return False
        self.save_current(touch=False)
        try:
            self.backups.create(self.db, kind="safety")
            new_index = self.db.delete_page(self._doc.id, self._index)
        except StorageError as exc:
            if interactive:
                QMessageBox.critical(
                    self,
                    "Excluir página",
                    "A exclusão foi cancelada.\n\n" + str(exc),
                )
                return False
            raise
        self._reload(new_index)
        return True

    def add_block(self) -> None:
        if not self.has_document or self._doc is None:
            return
        self.save_current(touch=True)
        page = self._doc.pages[self._index]
        if page.id is None:
            return
        self.db.add_extra_block(page.id)
        self._reload(self._index)

    def remove_extra_block(self, block_id: int) -> None:
        if self.sender() is not self._view:
            return
        if not self.has_document:
            return
        self.save_current(touch=True)
        try:
            self.db.delete_block(block_id)
        except StorageError as exc:
            QMessageBox.warning(self, "Remover bloco", str(exc))
            return
        self._reload(self._index)

    def _insert_at(self, position: int) -> None:
        if not self.has_document or self._doc is None or self._doc.id is None:
            return
        self.save_current(touch=True)
        new_index = self.db.insert_page(self._doc.id, position)
        self._reload(new_index)

    def _reload(self, index: int) -> None:
        if self._doc is None or self._doc.id is None:
            return
        document = self.db.load_document(self._doc.id)
        document.current_page_index = clamp_index(index, len(document.pages))
        self.db.set_current_page(document.id, document.current_page_index)
        self.load(document)
        self.structure_changed.emit()

    def _render(self, *, animated: bool) -> None:
        if self._doc is None:
            return
        focus = QApplication.focusWidget()
        role = focus.role if isinstance(focus, BlockEditor) else None
        view = PageView(self._doc.pages[self._index])
        view.content_changed.connect(self._on_content)
        view.active_block_changed.connect(self._set_active)
        view.remove_block_requested.connect(self.remove_extra_block)
        self._view = view
        self.host.show_widget(view, animated=animated)
        self._set_active(view.block("body"))
        if role is not None:
            try:
                view.block(role).setFocus()
            except KeyError:
                pass

    def _on_content(self) -> None:
        if self.sender() is not self._view:
            return
        self._dirty = True
        self.content_changed.emit()

    def _set_active(self, editor: BlockEditor) -> None:
        if editor is self._active:
            self._sync_toolbar()
            return
        if self._active is not None:
            self._disconnect_active()
        self._active = editor
        editor.cursorPositionChanged.connect(self._sync_toolbar)
        editor.currentCharFormatChanged.connect(self._sync_toolbar)
        self._sync_toolbar()

    def _disconnect_active(self) -> None:
        if self._active is None:
            return
        try:
            self._active.cursorPositionChanged.disconnect(self._sync_toolbar)
            self._active.currentCharFormatChanged.disconnect(self._sync_toolbar)
        except (RuntimeError, TypeError):
            return

    def _sync_toolbar(self, *_args) -> None:
        block = self._active
        if block is None:
            return
        bold, italic, underline = block.char_flags_at_cursor()
        self.toolbar.set_inline(bold, italic, underline)
        self.toolbar.set_alignment(block.alignment_name())
        self.toolbar.set_font_size(block.font_size_value())
        self.toolbar.set_list_kind(block.list_kind())

    def _apply(self, action) -> None:
        block = self._active
        if block is None and self._view is not None:
            block = self._view.block("body")
            self._set_active(block)
        if block is None:
            return
        action(block)
        self._sync_toolbar()

    def _update_controls(self) -> None:
        count = self.page_count
        if count <= 0:
            self.indicator.setText("0 / 0")
        else:
            self.indicator.setText(f"{self._index + 1} / {count}")
        has_pages = count > 0
        self.btn_prev.setEnabled(has_pages and self._index > 0)
        self.btn_next.setEnabled(has_pages and self._index < count - 1)
        self.btn_first.setEnabled(has_pages and self._index > 0)
        self.btn_last.setEnabled(has_pages and self._index < count - 1)
        for button in (
            self.btn_new_page,
            self.btn_duplicate,
            self.btn_insert_before,
            self.btn_insert_after,
            self.btn_delete_page,
            self.toolbar.add_block_button,
        ):
            button.setEnabled(self.has_document)
        self.toolbar.setEnabled(self.has_document)

    @staticmethod
    def _arrow(text: str, tip: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    @staticmethod
    def _button(text: str, tip: str) -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button
