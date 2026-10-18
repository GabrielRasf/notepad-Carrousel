"""Documentos, páginas e transações."""

from __future__ import annotations

import sqlite3

import pytest

from notepad_carrossel.models import Block, Page
from notepad_carrossel.storage.database import Database, StorageError


def test_create_edit_and_reopen(tmp_path):
    path = tmp_path / "área de trabalho" / "Meus Documentos" / "notepad.sqlite"
    database = Database(path)
    document = database.create_document("Notas do João")
    body = document.pages[0].blocks[2]
    body.html = "<p>Texto com acentuação: ação, coração.</p>"
    body.alignment = "justify"
    body.font_size = 18
    database.save_blocks(document.id, document.pages[0].blocks, touch=True)
    database.set_current_page(document.id, 0)
    created = document.created_at
    database.close()

    reopened = Database(path)
    again = reopened.load_document(document.id)
    assert again.name == "Notas do João"
    assert again.created_at == created
    assert again.updated_at >= created
    assert again.pages[0].blocks[2].alignment == "justify"
    assert again.pages[0].blocks[2].font_size == 18
    assert "coração" in again.pages[0].blocks[2].html
    assert reopened.get_state("last_document_id") == str(document.id)
    reopened.close()


def test_pages_are_ordered_duplicated_and_deleted(tmp_path):
    database = Database(tmp_path / "dados com espaço" / "notepad.sqlite")
    document = database.create_document("Páginas")
    first = document.pages[0]
    first.blocks[0].html = "<p>Um</p>"
    database.save_blocks(document.id, first.blocks, touch=True)
    database.insert_page(document.id, 1)
    loaded = database.load_document(document.id)
    loaded.pages[1].blocks[0].html = "<p>Dois</p>"
    database.save_blocks(document.id, loaded.pages[1].blocks, touch=True)
    database.insert_page(document.id, 1)
    loaded = database.load_document(document.id)
    loaded.pages[1].blocks[0].html = "<p>Meio</p>"
    database.save_blocks(document.id, loaded.pages[1].blocks, touch=True)

    loaded = database.load_document(document.id)
    assert [page.position for page in loaded.pages] == [0, 1, 2]
    assert [page.blocks[0].html for page in loaded.pages] == ["<p>Um</p>", "<p>Meio</p>", "<p>Dois</p>"]

    duplicate_index = database.duplicate_page(document.id, 0)
    assert duplicate_index == 1
    loaded = database.load_document(document.id)
    assert loaded.pages[1].blocks[0].html == "<p>Um</p>"
    assert loaded.pages[1].blocks[0].id != loaded.pages[0].blocks[0].id
    assert [page.position for page in loaded.pages] == [0, 1, 2, 3]

    database.set_current_page(document.id, 2)
    new_index = database.delete_page(document.id, 1)
    loaded = database.load_document(document.id)
    assert new_index == loaded.current_page_index
    assert [page.blocks[0].html for page in loaded.pages] == ["<p>Um</p>", "<p>Meio</p>", "<p>Dois</p>"]
    assert [page.position for page in loaded.pages] == [0, 1, 2]

    database.delete_page(document.id, 0)
    database.delete_page(document.id, 0)
    with pytest.raises(StorageError):
        database.delete_page(document.id, 0)
    assert len(database.load_document(document.id).pages) == 1
    database.close()


def test_extra_blocks_are_independent_rows(tmp_path):
    database = Database(tmp_path / "db.sqlite")
    document = database.create_document("Blocos")
    page_id = document.pages[0].id
    extra = database.add_extra_block(page_id)
    extra.html = "<p>Nota lateral</p>"
    extra.alignment = "right"
    extra.font_size = 12
    database.save_blocks(document.id, [extra], touch=True)
    loaded = database.load_document(document.id)
    assert [block.role for block in loaded.pages[0].blocks] == ["title", "subtitle", "body", "extra"]
    assert loaded.pages[0].blocks[3].alignment == "right"
    assert loaded.pages[0].blocks[0].alignment == "center"
    database.delete_block(extra.id)
    loaded = database.load_document(document.id)
    assert [block.role for block in loaded.pages[0].blocks] == ["title", "subtitle", "body"]
    with pytest.raises(StorageError):
        database.delete_block(loaded.pages[0].blocks[0].id)
    database.close()


def test_transaction_rolls_back(tmp_path):
    database = Database(tmp_path / "db.sqlite")
    document = database.create_document("Original")
    with pytest.raises(RuntimeError):
        with database.transaction():
            database.rename_document(document.id, "Não deve ficar")
            raise RuntimeError("falha")
    assert database.load_document(document.id).name == "Original"
    database.close()


def test_delete_document_removes_pages(tmp_path):
    path = tmp_path / "db.sqlite"
    database = Database(path)
    document = database.create_document("Apagar")
    database.delete_document(document.id)
    assert database.list_documents() == []
    database.close()
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0
    finally:
        connection.close()


def test_rejects_blank_name_and_bad_alignment(tmp_path):
    database = Database(tmp_path / "db.sqlite")
    document = database.create_document("Ok")
    with pytest.raises(StorageError):
        database.rename_document(document.id, "   ")
    block = document.pages[0].blocks[0]
    block.alignment = "diagonal"
    with pytest.raises(StorageError):
        database.save_blocks(document.id, [block], touch=True)
    database.close()


def test_import_pages_preserves_structure(tmp_path):
    database = Database(tmp_path / "db.sqlite")
    pages = [
        Page(
            position=0,
            blocks=[
                Block(role="title", html="<p>A</p>", alignment="center", font_size=30),
                Block(role="body", html="<p>B</p>", alignment="justify", font_size=14),
            ],
        )
    ]
    document = database.import_pages("Importado", pages, current_page_index=0)
    assert [block.role for block in document.pages[0].blocks][:3] == ["title", "subtitle", "body"]
    assert document.pages[0].blocks[0].alignment == "center"
    assert document.pages[0].blocks[2].alignment == "justify"
    assert document.pages[0].blocks[2].html == "<p>B</p>"
    database.close()
