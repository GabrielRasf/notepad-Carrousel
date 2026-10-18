"""Janela principal: biblioteca, editor e salvamento automático."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from notepad_carrossel.logging_util import log_exception
from notepad_carrossel.navigation import page_turn_direction
from notepad_carrossel.paths import StorageLayout, ensure_layout
from notepad_carrossel.storage.backup import BackupManager
from notepad_carrossel.storage.database import Database, StorageError, file_integrity_ok
from notepad_carrossel.storage.exchange import export_document, import_document
from notepad_carrossel.ui.dialogs import ask_confirmation
from notepad_carrossel.ui.editor_screen import EditorScreen
from notepad_carrossel.ui.library_view import LibraryView


class MainWindow(QMainWindow):
    def __init__(self, layout: StorageLayout):
        super().__init__()
        self.layout = layout
        ensure_layout(layout)
        self.backups = BackupManager(layout.backup_dir)
        self.db = self._open_database()
        self.autosave_delay_ms = 600
        self._editing = False
        self._current_id: int | None = None
        self._changed_since_backup = False
        self._save_error_shown = False
        self._closing = False

        self.setWindowTitle("Notepad Carrossel")
        self.resize(1180, 800)
        self.setMinimumSize(960, 640)
        self._build_ui()
        self._build_menu()
        self._install_filter()
        self._place_on_screen()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._autosave)
        self._backup_timer = QTimer(self)
        self._backup_timer.setInterval(10 * 60 * 1000)
        self._backup_timer.timeout.connect(self._periodic_backup)
        self._backup_timer.start()
        self.show_library()

    def current_document_id(self) -> int | None:
        return self._current_id

    def save_indicator_text(self) -> str:
        return self._save_label.text()

    def new_document(self, name: str | None = None):
        if name is None:
            suggested = self.db.unique_default_name()
            typed, accepted = QInputDialog.getText(self, "Novo documento", "Nome:", text=suggested)
            if not accepted:
                return None
            name = typed
        if self._editing and not self._flush(touch=self.editor.dirty):
            return None
        try:
            document = self.db.create_document(name)
        except StorageError as exc:
            self._report("Novo documento", exc)
            return None
        self.open_document(document.id)
        return document

    def open_document(self, document_id: int) -> None:
        if self._editing and self._current_id not in (None, document_id):
            if not self._flush(touch=self.editor.dirty):
                return
        try:
            document = self.db.load_document(document_id)
        except StorageError as exc:
            self._report("Abrir documento", exc)
            return
        self._current_id = document.id
        self.db.set_state("last_document_id", str(document.id))
        self.editor.load(document)
        self._editing = True
        self.stack.setCurrentWidget(self.editor)
        self._set_save_state("saved")
        self._update_chrome()

    def show_library(self) -> None:
        if self._editing and not self._flush(touch=self.editor.dirty):
            return
        self._editing = False
        self.library.reload()
        self.stack.setCurrentWidget(self.library)
        self._update_chrome()

    def save_now(self) -> None:
        self._timer.stop()
        if not self._editing:
            self._set_save_state("saved")
            return
        try:
            self.editor.save_current(touch=True)
        except StorageError as exc:
            self._fail_save(exc)
        else:
            self._changed_since_backup = True
            self._set_save_state("saved")

    def rename_document(self, name: str | None = None, document_id: int | None = None) -> None:
        target = document_id if document_id is not None else self._target_document_id()
        if target is None:
            return
        current = self.db.load_document(target)
        if name is None:
            typed, accepted = QInputDialog.getText(self, "Renomear documento", "Nome:", text=current.name)
            if not accepted:
                return
            name = typed
        try:
            self.db.rename_document(target, name)
        except StorageError as exc:
            self._report("Renomear", exc)
            return
        if self.library.isVisible():
            self.library.reload()
        self._update_chrome()

    def delete_document(self, document_id: int | None = None, *, interactive: bool = True) -> bool:
        target = document_id if document_id is not None else self._target_document_id()
        if target is None:
            return False
        document = self.db.load_document(target)
        if interactive and not ask_confirmation(
            self,
            "Excluir documento",
            f"Excluir “{document.name}”?\n\nEsta ação não pode ser desfeita. "
            "Uma cópia de segurança será criada antes da exclusão.",
            accept="Excluir",
        ):
            return False
        if self._current_id == target and self._editing and not self._flush(touch=self.editor.dirty):
            return False
        try:
            self.backups.create(self.db, kind="safety")
            self.db.delete_document(target)
        except StorageError as exc:
            if interactive:
                self._report("Excluir documento", exc)
                return False
            raise
        if self._current_id == target:
            self.editor.unload()
            self._current_id = None
            self._editing = False
        self.show_library()
        return True

    def export_current(self, path: Path | None = None, *, interactive: bool = True) -> Path | None:
        target = self._target_document_id()
        if target is None:
            if interactive:
                QMessageBox.information(self, "Exportar", "Escolha um documento para exportar.")
            return None
        if self._editing and self._current_id == target and not self._flush(touch=self.editor.dirty):
            return None
        document = self.db.load_document(target)
        destination = path
        if destination is None:
            suggested = f"{document.name}.notecarrossel.json"
            chosen, _selected = QFileDialog.getSaveFileName(
                self,
                "Exportar documento",
                suggested,
                "Documento do Notepad Carrossel (*.notecarrossel.json);;JSON (*.json)",
            )
            if not chosen:
                return None
            destination = Path(chosen)
        try:
            export_document(document, destination)
        except StorageError as exc:
            self._report("Exportar", exc)
            return None
        if interactive:
            QMessageBox.information(self, "Exportar", f"Documento exportado para:\n{destination}")
        return destination

    def import_from(self, path: Path | None = None, *, interactive: bool = True):
        source = path
        if source is None:
            chosen, _selected = QFileDialog.getOpenFileName(
                self,
                "Importar documento",
                "",
                "Documento do Notepad Carrossel (*.notecarrossel.json *.json)",
            )
            if not chosen:
                return None
            source = Path(chosen)
        try:
            document = import_document(self.db, source)
        except StorageError as exc:
            if interactive:
                self._report("Importar", exc)
            else:
                raise
            return None
        self.open_document(document.id)
        return document

    def backup_now(self, *, interactive: bool = True) -> Path | None:
        if self._editing and not self._flush(touch=self.editor.dirty):
            return None
        try:
            path = self.backups.create(self.db, kind="manual")
        except StorageError as exc:
            if interactive:
                self._report("Backup", exc)
            else:
                raise
            return None
        self._changed_since_backup = False
        if interactive:
            QMessageBox.information(self, "Backup", f"Cópia criada em:\n{path}")
        return path

    def restore_from(self, path: Path | None = None, *, interactive: bool = True) -> bool:
        source = path
        if source is None:
            chosen, _selected = QFileDialog.getOpenFileName(
                self,
                "Restaurar cópia de segurança",
                str(self.layout.backup_dir),
                "Cópia de segurança (*.sqlite)",
            )
            if not chosen:
                return False
            source = Path(chosen)
        if interactive and not ask_confirmation(
            self,
            "Restaurar",
            "Restaurar esta cópia substitui os documentos atuais.\n\n"
            "O estado atual será copiado antes, se ainda estiver íntegro.",
            accept="Restaurar",
        ):
            return False
        if self._editing:
            if not self._flush(touch=True):
                return False
            self.editor.unload()
            self._editing = False
            self._current_id = None
        try:
            self.backups.restore(source, self.db)
        except StorageError as exc:
            if interactive:
                self._report("Restaurar", exc)
            else:
                raise
            self.show_library()
            return False
        self._current_id = None
        self._changed_since_backup = False
        self.show_library()
        if interactive:
            QMessageBox.information(self, "Restaurar", "A cópia de segurança foi restaurada.")
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - API do Qt
        if self._closing:
            event.accept()
            return
        try:
            self._timer.stop()
            if self._editing and self.editor.has_document:
                self.editor.save_current(touch=self.editor.dirty)
            if self._changed_since_backup and self.db.is_open:
                try:
                    self.backups.create(self.db, kind="auto")
                except StorageError as exc:
                    log_exception(self.layout, "Backup automático ao fechar falhou", exc)
            if self.db.is_open:
                self.db.close()
        except Exception as exc:
            log_exception(self.layout, "Falha ao fechar", exc)
            answer = QMessageBox.question(
                self,
                "Erro ao salvar",
                "Não foi possível salvar as alterações. Fechar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closing = True
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        event.accept()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - API do Qt
        if (
            self._editing
            and not self._closing
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and QApplication.activeModalWidget() is None
            and QApplication.activePopupWidget() is None
            and not (event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            direction = page_turn_direction(event.key(), event.modifiers(), QApplication.focusWidget())
            if direction:
                self.editor.step(direction)
                return True
        return super().eventFilter(watched, event)

    def _open_database(self) -> Database:
        path = self.layout.database_path
        if path.exists() and not file_integrity_ok(path):
            quarantined = self.backups.quarantine(path)
            latest = self.backups.latest_valid()
            restored = False
            if latest is not None and ask_confirmation(
                self,
                "Banco danificado",
                "O arquivo de documentos não passou na verificação.\n\n"
                "Posso restaurar a cópia de segurança mais recente.",
                accept="Restaurar",
            ):
                try:
                    self.backups.install(latest, path)
                    restored = True
                except StorageError as exc:
                    QMessageBox.critical(self, "Restaurar", str(exc))
            if not restored:
                QMessageBox.warning(
                    self,
                    "Banco danificado",
                    "O arquivo danificado foi isolado em:\n"
                    f"{quarantined}\n\nUm banco novo e vazio será usado.",
                )
        return Database(path)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        self.btn_library = QPushButton("← Biblioteca")
        self.btn_library.setObjectName("quiet")
        self.btn_library.clicked.connect(lambda *_args: self.show_library())
        self.title_button = QPushButton("Notepad Carrossel")
        self.title_button.setObjectName("quiet")
        self.title_button.clicked.connect(lambda *_args: self._rename_from_header())
        self._save_label = QLabel("")
        self._save_label.setObjectName("saveOk")
        header_layout.addWidget(self.btn_library)
        header_layout.addWidget(self.title_button, 1)
        header_layout.addWidget(self._save_label)
        outer.addWidget(header)

        self.library = LibraryView(self.db, self.layout)
        self.editor = EditorScreen(self.db, self.backups)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.library)
        self.stack.addWidget(self.editor)
        outer.addWidget(self.stack, 1)

        self.library.open_requested.connect(self.open_document)
        self.library.new_requested.connect(lambda *_args: self.new_document(None))
        self.library.rename_requested.connect(lambda *_args: self.rename_document(None))
        self.library.delete_requested.connect(lambda *_args: self.delete_document(interactive=True))
        self.library.import_requested.connect(lambda *_args: self.import_from(None))
        self.library.export_requested.connect(lambda *_args: self.export_current(None))
        self.library.backup_requested.connect(lambda *_args: self.backup_now())
        self.library.restore_requested.connect(lambda *_args: self.restore_from(None))
        self.editor.content_changed.connect(self._on_dirty)
        self.editor.structure_changed.connect(self._on_structure)
        self.editor.index_changed.connect(lambda _index: self._update_chrome())

        status = self.statusBar()
        status.showMessage(f"Dados em {self.layout.data_dir}")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Arquivo")
        self.act_new = file_menu.addAction("Novo documento")
        self.act_new.setShortcut("Ctrl+N")
        self.act_new.triggered.connect(lambda *_args: self.new_document(None))
        self.act_library = file_menu.addAction("Biblioteca")
        self.act_library.setShortcut("Ctrl+O")
        self.act_library.triggered.connect(lambda *_args: self.show_library())
        self.act_rename = file_menu.addAction("Renomear")
        self.act_rename.triggered.connect(lambda *_args: self.rename_document(None))
        self.act_save = file_menu.addAction("Salvar agora")
        self.act_save.setShortcut("Ctrl+S")
        self.act_save.triggered.connect(lambda *_args: self.save_now())
        file_menu.addSeparator()
        self.act_export = file_menu.addAction("Exportar documento")
        self.act_export.triggered.connect(lambda *_args: self.export_current(None))
        self.act_import = file_menu.addAction("Importar documento")
        self.act_import.triggered.connect(lambda *_args: self.import_from(None))
        file_menu.addSeparator()
        self.act_backup = file_menu.addAction("Backup agora")
        self.act_backup.triggered.connect(lambda *_args: self.backup_now())
        self.act_restore = file_menu.addAction("Restaurar backup")
        self.act_restore.triggered.connect(lambda *_args: self.restore_from(None))
        file_menu.addSeparator()
        self.act_delete_doc = file_menu.addAction("Excluir documento")
        self.act_delete_doc.triggered.connect(lambda *_args: self.delete_document(interactive=True))
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Sair")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(lambda *_args: self.close())

        page_menu = self.menuBar().addMenu("Página")
        self.act_new_page = page_menu.addAction("Nova página")
        self.act_new_page.setShortcut("Ctrl+T")
        self.act_new_page.triggered.connect(lambda *_args: self.editor.new_page())
        self.act_duplicate = page_menu.addAction("Duplicar página")
        self.act_duplicate.setShortcut("Ctrl+D")
        self.act_duplicate.triggered.connect(lambda *_args: self.editor.duplicate_page())
        self.act_before = page_menu.addAction("Inserir antes")
        self.act_before.triggered.connect(lambda *_args: self.editor.insert_before())
        self.act_after = page_menu.addAction("Inserir depois")
        self.act_after.triggered.connect(lambda *_args: self.editor.insert_after())
        self.act_delete_page = page_menu.addAction("Excluir página")
        self.act_delete_page.triggered.connect(lambda *_args: self.editor.delete_page(interactive=True))
        page_menu.addSeparator()
        self.act_prev = page_menu.addAction("Página anterior")
        self.act_prev.setShortcut("Alt+Left")
        self.act_prev.triggered.connect(lambda *_args: self.editor.step(-1))
        self.act_next = page_menu.addAction("Próxima página")
        self.act_next.setShortcut("Alt+Right")
        self.act_next.triggered.connect(lambda *_args: self.editor.step(1))
        self.act_first = page_menu.addAction("Primeira página")
        self.act_first.setShortcut("Ctrl+Alt+Left")
        self.act_first.triggered.connect(lambda *_args: self.editor.go_first())
        self.act_last = page_menu.addAction("Última página")
        self.act_last.setShortcut("Ctrl+Alt+Right")
        self.act_last.triggered.connect(lambda *_args: self.editor.go_last())
        self._page_actions = (
            self.act_new_page,
            self.act_duplicate,
            self.act_before,
            self.act_after,
            self.act_delete_page,
            self.act_prev,
            self.act_next,
            self.act_first,
            self.act_last,
        )

    def _install_filter(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _place_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _on_dirty(self) -> None:
        self._changed_since_backup = True
        self._set_save_state("saving")
        self._timer.setInterval(self.autosave_delay_ms)
        self._timer.start()

    def _on_structure(self) -> None:
        self._changed_since_backup = True
        self._set_save_state("saved")
        self._update_chrome()

    def _autosave(self) -> None:
        if not self._editing or not self.editor.dirty:
            if self._editing:
                self._set_save_state("saved")
            return
        try:
            self.editor.save_current(touch=True)
        except StorageError as exc:
            self._fail_save(exc)
        else:
            self._set_save_state("saved")

    def _periodic_backup(self) -> None:
        if not self._changed_since_backup or not self.db.is_open:
            return
        try:
            if self._editing:
                self._flush(touch=self.editor.dirty)
            self.backups.create(self.db, kind="auto")
        except StorageError as exc:
            log_exception(self.layout, "Backup automático falhou", exc)
            return
        self._changed_since_backup = False

    def _flush(self, *, touch: bool) -> bool:
        if not self._editing or not self.editor.has_document:
            return True
        try:
            self.editor.save_current(touch=touch)
        except StorageError as exc:
            self._fail_save(exc)
            return False
        return True

    def _fail_save(self, exc: BaseException) -> None:
        self._set_save_state("error")
        self._save_label.setToolTip(str(exc))
        log_exception(self.layout, "Erro ao salvar", exc)
        if not self._save_error_shown:
            self._save_error_shown = True
            QMessageBox.warning(self, "Erro ao salvar", f"Não foi possível salvar.\n\n{exc}")

    def _set_save_state(self, state: str) -> None:
        mapping = {
            "saving": ("Salvando", "savePending"),
            "saved": ("Salvo", "saveOk"),
            "error": ("Erro ao salvar", "saveError"),
            "idle": ("", "saveOk"),
        }
        text, name = mapping[state]
        self._save_label.setText(text)
        self._save_label.setObjectName(name)
        self._save_label.style().unpolish(self._save_label)
        self._save_label.style().polish(self._save_label)
        if state == "saved":
            self._save_error_shown = False
            self._save_label.setToolTip("")

    def _update_chrome(self) -> None:
        editing = self._editing and self._current_id is not None
        self.btn_library.setVisible(editing)
        self.act_save.setEnabled(editing)
        for action in self._page_actions:
            action.setEnabled(editing)
        if not editing or not self.db.is_open:
            self.title_button.setText("Notepad Carrossel")
            self._set_save_state("idle")
            self.setWindowTitle("Notepad Carrossel")
            return
        try:
            document = self.db.load_document(self._current_id)
        except StorageError:
            return
        self.title_button.setText(document.name)
        self.setWindowTitle(f"Notepad Carrossel — {document.name}")
        at_start = self.editor.current_index <= 0
        at_end = self.editor.current_index >= self.editor.page_count - 1
        self.act_prev.setEnabled(not at_start)
        self.act_next.setEnabled(not at_end)
        self.act_first.setEnabled(not at_start)
        self.act_last.setEnabled(not at_end)

    def _rename_from_header(self) -> None:
        if self._editing and self._current_id is not None:
            self.rename_document(None, self._current_id)

    def _target_document_id(self) -> int | None:
        if self._editing and self._current_id is not None:
            return self._current_id
        return self.library.selected_id()

    def _report(self, title: str, exc: BaseException) -> None:
        log_exception(self.layout, title, exc)
        QMessageBox.warning(self, title, str(exc))
