"""Biblioteca de documentos recentes."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from notepad_carrossel.paths import StorageLayout
from notepad_carrossel.storage.database import Database


def format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def pages_label(count: int) -> str:
    if count == 1:
        return "1 página"
    return f"{count} páginas"


class LibraryView(QWidget):
    open_requested = Signal(int)
    new_requested = Signal()
    rename_requested = Signal()
    delete_requested = Signal()
    import_requested = Signal()
    export_requested = Signal()
    backup_requested = Signal()
    restore_requested = Signal()

    def __init__(self, database: Database, layout: StorageLayout):
        super().__init__()
        self.db = database
        self.storage = layout

        title = QLabel("Documentos")
        title.setObjectName("appTitle")
        subtitle = QLabel("Os textos ficam neste computador, junto da pasta do programa.")
        subtitle.setObjectName("metaLabel")
        subtitle.setWordWrap(True)

        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filtrar documentos")
        self.filter_box.textChanged.connect(self._apply_filter)

        self.list = QListWidget()
        self.list.setObjectName("documentList")
        self.list.itemActivated.connect(self._activate)
        self.list.currentItemChanged.connect(lambda *_: self._update_buttons())
        self.empty = QLabel("Nenhum documento ainda.\nCrie o primeiro para começar.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("metaLabel")

        self.path_label = QLabel(str(layout.root))
        self.path_label.setObjectName("pathLabel")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.btn_continue = QPushButton("Continuar")
        self.btn_continue.setObjectName("primary")
        self.btn_new = QPushButton("Novo documento")
        self.btn_rename = QPushButton("Renomear")
        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.setObjectName("danger")
        self.btn_import = QPushButton("Importar")
        self.btn_export = QPushButton("Exportar")
        self.btn_backup = QPushButton("Backup")
        self.btn_restore = QPushButton("Restaurar")

        self.btn_continue.clicked.connect(lambda *_args: self._open_selected())
        self.btn_new.clicked.connect(lambda *_args: self.new_requested.emit())
        self.btn_rename.clicked.connect(lambda *_args: self.rename_requested.emit())
        self.btn_delete.clicked.connect(lambda *_args: self.delete_requested.emit())
        self.btn_import.clicked.connect(lambda *_args: self.import_requested.emit())
        self.btn_export.clicked.connect(lambda *_args: self.export_requested.emit())
        self.btn_backup.clicked.connect(lambda *_args: self.backup_requested.emit())
        self.btn_restore.clicked.connect(lambda *_args: self.restore_requested.emit())

        actions = QHBoxLayout()
        actions.setSpacing(8)
        for button in (
            self.btn_continue,
            self.btn_new,
            self.btn_rename,
            self.btn_delete,
            self.btn_import,
            self.btn_export,
            self.btn_backup,
            self.btn_restore,
        ):
            actions.addWidget(button)
        actions.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(12)
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self.filter_box)
        root.addWidget(self.list, 1)
        root.addWidget(self.empty)
        root.addLayout(actions)
        root.addWidget(self.path_label)
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        documents = self.db.list_documents()
        last_id = self.db.get_state("last_document_id") or ""
        selected_row = 0
        for row, document in enumerate(documents):
            item = QListWidgetItem(
                f"{document.name}\n{pages_label(document.page_count)} · alterado em {format_timestamp(document.updated_at)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, document.id)
            item.setSizeHint(QSize(0, 68))
            self.list.addItem(item)
            if str(document.id) == last_id:
                selected_row = row
        self.empty.setVisible(not documents)
        self.list.setVisible(bool(documents))
        if documents:
            self.list.setCurrentRow(selected_row)
        self._apply_filter(self.filter_box.text())
        self._update_buttons()

    def selected_id(self) -> int | None:
        item = self.list.currentItem()
        if item is None or item.isHidden():
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is None:
            return None
        return int(value)

    def _open_selected(self) -> None:
        document_id = self.selected_id()
        if document_id is not None:
            self.open_requested.emit(document_id)

    def _activate(self, item: QListWidgetItem) -> None:
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is not None:
            self.open_requested.emit(int(value))

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.list.count()):
            item = self.list.item(index)
            item.setHidden(bool(needle) and needle not in item.text().casefold())
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self.selected_id() is not None
        self.btn_continue.setEnabled(has_selection)
        self.btn_rename.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        self.btn_export.setEnabled(has_selection)
