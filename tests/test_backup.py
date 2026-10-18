"""Backup, restauração, exportação e importação."""

from __future__ import annotations

import json

import pytest

from notepad_carrossel.storage.backup import BackupManager
from notepad_carrossel.storage.database import Database, StorageError, file_integrity_ok
from notepad_carrossel.storage.exchange import FORMAT_ID, export_document, import_document


def test_backup_and_restore_keep_formatting(tmp_path):
    database = Database(tmp_path / "data" / "notepad.sqlite")
    backups = BackupManager(tmp_path / "backup")
    document = database.create_document("Original")
    title = document.pages[0].blocks[0]
    title.html = "<p><b>Centro</b></p>"
    title.alignment = "center"
    title.font_size = 28
    body = document.pages[0].blocks[2]
    body.html = "<p><i>Justificado</i></p>"
    body.alignment = "justify"
    body.font_size = 16
    database.save_blocks(document.id, document.pages[0].blocks, touch=True)
    backup = backups.create(database, kind="manual")
    assert file_integrity_ok(backup)

    database.rename_document(document.id, "Alterado")
    title = database.load_document(document.id).pages[0].blocks[0]
    title.html = "<p>sumiu</p>"
    database.save_blocks(document.id, [title], touch=True)

    backups.restore(backup, database)
    restored = database.load_document(document.id)
    assert restored.name == "Original"
    assert restored.pages[0].blocks[0].alignment == "center"
    assert restored.pages[0].blocks[0].font_size == 28
    assert "Centro" in restored.pages[0].blocks[0].html
    assert restored.pages[0].blocks[2].alignment == "justify"
    database.close()


def test_corrupt_source_does_not_replace_valid_backup(tmp_path, monkeypatch):
    database = Database(tmp_path / "data" / "notepad.sqlite")
    backups = BackupManager(tmp_path / "backup")
    database.create_document("Seguro")
    backup = backups.create(database, kind="manual")
    snapshot = backup.read_bytes()
    monkeypatch.setattr(database, "integrity_ok", lambda: False)
    with pytest.raises(StorageError):
        backups.create(database, kind="manual")
    assert backup.read_bytes() == snapshot
    assert list((tmp_path / "backup").glob("manual-*.sqlite")) == [backup]
    database.close()


def test_corrupt_backup_is_not_restored(tmp_path):
    database = Database(tmp_path / "data" / "notepad.sqlite")
    backups = BackupManager(tmp_path / "backup")
    document = database.create_document("Fica")
    junk = tmp_path / "backup" / "manual-lixo.sqlite"
    junk.write_text("não é sqlite", encoding="utf-8")
    with pytest.raises(StorageError):
        backups.restore(junk, database)
    assert database.load_document(document.id).name == "Fica"
    assert file_integrity_ok(database.path)
    database.close()


def test_export_and_import_roundtrip(tmp_path):
    database = Database(tmp_path / "data" / "notepad.sqlite")
    document = database.create_document("Viagem")
    document.pages[0].blocks[0].html = "<p>Lisboa</p>"
    document.pages[0].blocks[0].alignment = "center"
    document.pages[0].blocks[0].font_size = 26
    document.pages[0].blocks[2].html = "<p>Texto longo.</p>"
    document.pages[0].blocks[2].alignment = "justify"
    database.save_blocks(document.id, document.pages[0].blocks, touch=False)
    database.insert_page(document.id, 1)
    destination = tmp_path / "área" / "viagem.notecarrossel.json"
    export_document(database.load_document(document.id), destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["format"] == FORMAT_ID
    assert payload["pages"][0]["blocks"][0]["alignment"] == "center"
    assert "Lisboa" in payload["pages"][0]["blocks"][0]["html"]

    database.delete_document(document.id)
    imported = import_document(database, destination)
    assert imported.name == "Viagem"
    assert len(imported.pages) == 2
    assert imported.pages[0].blocks[0].alignment == "center"
    assert imported.pages[0].blocks[0].font_size == 26
    assert imported.pages[0].blocks[2].alignment == "justify"
    assert "Lisboa" in imported.pages[0].blocks[0].html
    database.close()


def test_import_rejects_unknown_file_and_renames_collision(tmp_path):
    database = Database(tmp_path / "db.sqlite")
    database.create_document("Viagem")
    bad = tmp_path / "ruim.json"
    bad.write_text(json.dumps({"format": FORMAT_ID, "version": 99, "pages": []}), encoding="utf-8")
    with pytest.raises(StorageError):
        import_document(database, bad)
    good = tmp_path / "ok.json"
    document = database.list_documents()[0]
    export_document(database.load_document(document.id), good)
    imported = import_document(database, good)
    assert imported.name == "Viagem (importado)"
    database.close()
