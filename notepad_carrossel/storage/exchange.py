"""Exportação e importação de um documento, com formatação inclusa."""

from __future__ import annotations

import json
from pathlib import Path

from notepad_carrossel.models import (
    ALIGNMENTS,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    ROLES,
    Block,
    Document,
    Page,
    normalize_blocks,
)
from notepad_carrossel.storage.database import Database, StorageError

FORMAT_ID = "notepad-carrossel-document"
FORMAT_VERSION = 1


def export_document(document: Document, destination: Path) -> None:
    payload = {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "name": document.name,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "current_page_index": document.current_page_index,
        "pages": [
            {
                "blocks": [
                    {
                        "role": block.role,
                        "html": block.html,
                        "alignment": block.alignment,
                        "font_size": block.font_size,
                    }
                    for block in page.blocks
                ]
            }
            for page in document.pages
        ],
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def import_document(database: Database, source: Path) -> Document:
    path = Path(source)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StorageError(f"Não foi possível ler o arquivo: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StorageError("O arquivo não está em um formato reconhecível.") from exc
    if not isinstance(payload, dict):
        raise StorageError("O arquivo não está em um formato reconhecível.")
    if payload.get("format") != FORMAT_ID:
        raise StorageError("Este arquivo não é um documento do Notepad Carrossel.")
    if payload.get("version") != FORMAT_VERSION:
        raise StorageError("A versão deste arquivo não é compatível com o programa.")

    name = str(payload.get("name") or "Importado").strip() or "Importado"
    pages_payload = payload.get("pages")
    if not isinstance(pages_payload, list) or not pages_payload:
        raise StorageError("O arquivo não contém páginas.")

    pages: list[Page] = []
    for page_index, page_data in enumerate(pages_payload):
        if not isinstance(page_data, dict) or not isinstance(page_data.get("blocks"), list):
            raise StorageError(f"A página {page_index + 1} está incompleta.")
        blocks: list[Block] = []
        for block_data in page_data["blocks"]:
            blocks.append(_parse_block(block_data))
        pages.append(Page(position=page_index, blocks=normalize_blocks(blocks)))

    existing = {item.name for item in database.list_documents()}
    if name in existing:
        base = f"{name} (importado)"
        candidate = base
        number = 2
        while candidate in existing:
            candidate = f"{base} {number}"
            number += 1
        name = candidate

    try:
        current = int(payload.get("current_page_index") or 0)
    except (TypeError, ValueError):
        current = 0
    created = payload.get("created_at")
    created_at = created if isinstance(created, str) and created else None
    return database.import_pages(name, pages, current_page_index=current, created_at=created_at)


def _parse_block(data: object) -> Block:
    if not isinstance(data, dict):
        raise StorageError("Um bloco do arquivo está incompleto.")
    role = data.get("role")
    alignment = data.get("alignment", "left")
    if role not in ROLES:
        raise StorageError("Um bloco do arquivo tem um tipo desconhecido.")
    if alignment not in ALIGNMENTS:
        raise StorageError("Um bloco do arquivo tem um alinhamento desconhecido.")
    try:
        font_size = int(data.get("font_size", 15))
    except (TypeError, ValueError) as exc:
        raise StorageError("Um bloco do arquivo tem um tamanho de fonte inválido.") from exc
    if font_size < MIN_FONT_SIZE or font_size > MAX_FONT_SIZE:
        raise StorageError("Um bloco do arquivo tem um tamanho de fonte inválido.")
    html = data.get("html", "")
    if not isinstance(html, str):
        raise StorageError("O texto de um bloco está em formato inválido.")
    return Block(role=role, html=html, alignment=alignment, font_size=font_size)
