"""Verificação local do executável: dados, formatação, backup e caminho portátil."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from notepad_carrossel.paths import (
    StorageLayout,
    bundle_dir,
    ensure_layout,
    is_frozen,
    is_inside,
    resolve_storage,
)
from notepad_carrossel.storage.backup import BackupManager
from notepad_carrossel.storage.database import Database, StorageError
from notepad_carrossel.storage.exchange import export_document, import_document


def run_self_test(root: Path | None) -> int:
    layout: StorageLayout | None = None
    try:
        executable = None if root is None else root / "NotepadCarrossel.exe"
        layout, error = resolve_storage(executable=executable, allow_user_settings=False)
        if layout is None:
            raise RuntimeError(error or "Não foi possível escolher a pasta de dados.")
        ensure_layout(layout)
        _assert_storage_location(layout, forced_root=root)
        created = set(layout.backup_dir.glob("*.sqlite"))
        database = Database(layout.database_path)
        try:
            document = database.create_document("Autoteste açúcar e espaços")
            title = document.pages[0].blocks[0]
            subtitle = document.pages[0].blocks[1]
            body = document.pages[0].blocks[2]
            title.html = "<p><b>Título central</b></p>"
            title.alignment = "center"
            title.font_size = 28
            subtitle.html = "<p>Subtítulo à esquerda</p>"
            subtitle.alignment = "left"
            subtitle.font_size = 18
            body.html = "<p><i>Texto principal — memória</i></p>"
            body.alignment = "justify"
            body.font_size = 17
            database.save_blocks(document.id, document.pages[0].blocks, touch=True)
            database.insert_page(document.id, 1)
            document_id = document.id
            database.close()

            database = Database(layout.database_path)
            again = database.load_document(document_id)
            if again.pages[0].blocks[0].alignment != "center":
                raise AssertionError("O título não manteve o alinhamento.")
            if again.pages[0].blocks[1].alignment != "left":
                raise AssertionError("O subtítulo não manteve o alinhamento.")
            if again.pages[0].blocks[2].alignment != "justify" or again.pages[0].blocks[2].font_size != 17:
                raise AssertionError("O texto principal não manteve a formatação.")
            if "Título central" not in again.pages[0].blocks[0].html:
                raise AssertionError("O título não foi relido.")
            if len(again.pages) != 2:
                raise AssertionError("A segunda página desapareceu.")

            backups = BackupManager(layout.backup_dir)
            backup_path = backups.create(database, kind="manual")
            database.rename_document(document_id, "Nome alterado")
            backups.restore(backup_path, database)
            restored = database.load_document(document_id)
            if restored.name != "Autoteste açúcar e espaços":
                raise AssertionError("A restauração não devolveu o documento.")
            if restored.pages[0].blocks[2].alignment != "justify":
                raise AssertionError("A restauração perdeu a formatação.")

            junk = layout.backup_dir / "manual-lixo-selftest.sqlite"
            junk.write_text("isto não é um banco", encoding="utf-8")
            try:
                backups.restore(junk, database)
            except StorageError:
                pass
            else:
                raise AssertionError("Uma cópia inválida foi restaurada.")
            if database.load_document(document_id).name != "Autoteste açúcar e espaços":
                raise AssertionError("A cópia inválida alterou o banco.")
            junk.unlink(missing_ok=True)

            exported = layout.data_dir / "selftest-export.json"
            export_document(database.load_document(document_id), exported)
            database.delete_document(document_id)
            imported = import_document(database, exported)
            if imported.pages[0].blocks[0].alignment != "center":
                raise AssertionError("A importação perdeu o alinhamento do título.")
            if imported.pages[0].blocks[2].font_size != 17:
                raise AssertionError("A importação perdeu o tamanho da fonte.")
            database.delete_document(imported.id)
            exported.unlink(missing_ok=True)
        finally:
            if database.is_open:
                database.close()
        for extra in set(layout.backup_dir.glob("*.sqlite")) - created:
            extra.unlink(missing_ok=True)
        _write_result(layout, "SELFTEST_OK\n")
        print("SELFTEST_OK")
        return 0
    except Exception:
        message = traceback.format_exc()
        print(message, file=sys.stderr)
        if layout is not None:
            _write_result(layout, "SELFTEST_FAIL\n" + message)
        return 1


def _assert_storage_location(layout: StorageLayout, *, forced_root: Path | None) -> None:
    temporary = bundle_dir()
    if is_inside(layout.data_dir, temporary) or is_inside(layout.database_path, temporary):
        raise RuntimeError("Os dados foram parar na pasta temporária do PyInstaller.")
    if is_frozen() and forced_root is None:
        exe_dir = Path(sys.executable).resolve().parent
        if not is_inside(layout.database_path, exe_dir) and not layout.using_fallback:
            raise RuntimeError("O banco não está junto do executável.")
        if layout.app_dir != exe_dir:
            raise RuntimeError("A pasta do aplicativo não é a pasta do executável.")


def _write_result(layout: StorageLayout, text: str) -> None:
    try:
        layout.data_dir.mkdir(parents=True, exist_ok=True)
        (layout.data_dir / "selftest-result.txt").write_text(text, encoding="utf-8")
    except OSError:
        return
