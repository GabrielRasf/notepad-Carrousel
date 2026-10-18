"""SQLite local, com transações e verificação de integridade."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from notepad_carrossel.models import (
    ALIGNMENTS,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    ROLES,
    Block,
    Document,
    DocumentSummary,
    Page,
    default_blocks,
    normalize_blocks,
)
from notepad_carrossel.navigation import clamp_index, index_after_delete

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_page_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    UNIQUE (document_id, position)
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('title', 'subtitle', 'body', 'extra')),
    html TEXT NOT NULL DEFAULT '',
    alignment TEXT NOT NULL CHECK (alignment IN ('left', 'center', 'right', 'justify')),
    font_size INTEGER NOT NULL CHECK (font_size BETWEEN 8 AND 96),
    UNIQUE (page_id, position)
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pages_document ON pages(document_id, position);
CREATE INDEX IF NOT EXISTS idx_blocks_page ON blocks(page_id, position);
"""


class StorageError(Exception):
    """Falha de leitura, gravação ou validação dos dados locais."""


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def file_integrity_ok(path: Path) -> bool:
    """Confere se o arquivo é um banco deste aplicativo e passa no integrity_check."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size < 512:
            return False
    except OSError:
        return False
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error:
        return False
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            return False
        tables = {
            item[0]
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required = {"documents", "pages", "blocks", "app_state"}
        return required.issubset(tables)
    except sqlite3.Error:
        return False
    finally:
        connection.close()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None
        self._depth = 0
        self._connect(self.path)

    @property
    def is_open(self) -> bool:
        return self._conn is not None

    def _connect(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            connection = sqlite3.connect(path, timeout=5.0)
        except sqlite3.Error as exc:
            raise StorageError(f"Não foi possível abrir o banco de dados: {exc}") from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()
            if mode is None or str(mode[0]).lower() != "wal":
                connection.execute("PRAGMA journal_mode = DELETE")
        except sqlite3.Error:
            connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
        except sqlite3.DatabaseError as exc:
            connection.close()
            raise StorageError("O banco de dados está danificado.") from exc
        self.path = path
        self._conn = connection
        self._depth = 0

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise StorageError("O banco de dados está fechado.")
        return self._conn

    def close(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        self._conn.close()
        self._conn = None
        self._depth = 0

    def reopen(self) -> None:
        path = self.path
        self.close()
        self._connect(path)

    def integrity_ok(self) -> bool:
        try:
            row = self.connection.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error:
            return False
        return bool(row) and row[0] == "ok"

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connection
        own = self._depth == 0
        if own:
            connection.execute("BEGIN IMMEDIATE")
        self._depth += 1
        try:
            yield connection
        except Exception:
            self._depth -= 1
            if own:
                self._depth = 0
                connection.rollback()
            raise
        else:
            self._depth -= 1
            if own:
                connection.commit()

    def unique_default_name(self, base: str = "Sem título") -> str:
        taken = {item.name for item in self.list_documents()}
        if base not in taken:
            return base
        number = 2
        while f"{base} {number}" in taken:
            number += 1
        return f"{base} {number}"

    def create_document(self, name: str | None = None) -> Document:
        cleaned = (name or "").strip() or self.unique_default_name()
        self._validate_name(cleaned)
        now = timestamp()
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents (name, created_at, updated_at, current_page_index)
                VALUES (?, ?, ?, 0)
                """,
                (cleaned, now, now),
            )
            document_id = int(cursor.lastrowid)
            self._insert_page(connection, document_id, 0, default_blocks())
            self._write_state(connection, "last_document_id", str(document_id))
        return self.load_document(document_id)

    def list_documents(self) -> list[DocumentSummary]:
        rows = self.connection.execute(
            """
            SELECT d.id, d.name, d.created_at, d.updated_at, d.current_page_index,
                   (SELECT COUNT(*) FROM pages p WHERE p.document_id = d.id) AS page_count
            FROM documents d
            ORDER BY d.updated_at DESC, d.id DESC
            """
        ).fetchall()
        return [
            DocumentSummary(
                id=int(row["id"]),
                name=row["name"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                current_page_index=int(row["current_page_index"]),
                page_count=int(row["page_count"]),
            )
            for row in rows
        ]

    def load_document(self, document_id: int) -> Document:
        row = self.connection.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        if row is None:
            raise StorageError("Documento não encontrado.")
        pages = self._load_pages(document_id)
        return Document(
            id=int(row["id"]),
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            current_page_index=clamp_index(int(row["current_page_index"]), len(pages)),
            pages=pages,
        )

    def rename_document(self, document_id: int, name: str) -> None:
        cleaned = name.strip()
        self._validate_name(cleaned)
        with self.transaction() as connection:
            updated = connection.execute(
                "UPDATE documents SET name = ?, updated_at = ? WHERE id = ?",
                (cleaned, timestamp(), document_id),
            )
            if updated.rowcount != 1:
                raise StorageError("Documento não encontrado.")

    def delete_document(self, document_id: int) -> None:
        with self.transaction() as connection:
            deleted = connection.execute(
                "DELETE FROM documents WHERE id = ?",
                (document_id,),
            )
            if deleted.rowcount != 1:
                raise StorageError("Documento não encontrado.")
            current = self._read_state(connection, "last_document_id")
            if current == str(document_id):
                self._write_state(connection, "last_document_id", "")

    def set_current_page(self, document_id: int, index: int) -> None:
        document = self.load_document(document_id)
        safe = clamp_index(index, len(document.pages))
        with self.transaction() as connection:
            connection.execute(
                "UPDATE documents SET current_page_index = ? WHERE id = ?",
                (safe, document_id),
            )

    def insert_page(self, document_id: int, position: int, *, source: Page | None = None) -> int:
        document = self.load_document(document_id)
        position = max(0, min(position, len(document.pages)))
        blocks = source.copy().blocks if source is not None else default_blocks()
        for block in blocks:
            block.id = None
        with self.transaction() as connection:
            self._shift_pages_up(connection, document_id, position)
            self._insert_page(connection, document_id, position, blocks)
            connection.execute(
                """
                UPDATE documents
                SET current_page_index = ?, updated_at = ?
                WHERE id = ?
                """,
                (position, timestamp(), document_id),
            )
        return position

    def duplicate_page(self, document_id: int, position: int) -> int:
        document = self.load_document(document_id)
        if position < 0 or position >= len(document.pages):
            raise StorageError("Página não encontrada.")
        return self.insert_page(document_id, position + 1, source=document.pages[position])

    def delete_page(self, document_id: int, position: int) -> int:
        document = self.load_document(document_id)
        if len(document.pages) <= 1:
            raise StorageError("O documento precisa ter ao menos uma página.")
        if position < 0 or position >= len(document.pages):
            raise StorageError("Página não encontrada.")
        new_index = index_after_delete(document.current_page_index, position, len(document.pages) - 1)
        with self.transaction() as connection:
            deleted = connection.execute(
                "DELETE FROM pages WHERE document_id = ? AND position = ?",
                (document_id, position),
            )
            if deleted.rowcount != 1:
                raise StorageError("Página não encontrada.")
            self._shift_pages_down(connection, document_id, position)
            connection.execute(
                """
                UPDATE documents
                SET current_page_index = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_index, timestamp(), document_id),
            )
        return new_index

    def add_extra_block(self, page_id: int) -> Block:
        with self.transaction() as connection:
            position = self._next_block_position(connection, page_id)
            cursor = connection.execute(
                """
                INSERT INTO blocks (page_id, position, role, html, alignment, font_size)
                VALUES (?, ?, 'extra', '', 'left', 15)
                """,
                (page_id, position),
            )
            self._touch_page(connection, page_id)
            return Block(
                id=int(cursor.lastrowid),
                role="extra",
                html="",
                alignment="left",
                font_size=15,
                position=position,
            )

    def delete_block(self, block_id: int) -> None:
        row = self.connection.execute(
            "SELECT id, role, page_id, position FROM blocks WHERE id = ?",
            (block_id,),
        ).fetchone()
        if row is None:
            raise StorageError("Bloco não encontrado.")
        if row["role"] != "extra":
            raise StorageError("Somente blocos adicionais podem ser removidos.")
        with self.transaction() as connection:
            connection.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
            following = connection.execute(
                """
                SELECT id, position FROM blocks
                WHERE page_id = ? AND position > ?
                ORDER BY position ASC
                """,
                (row["page_id"], row["position"]),
            ).fetchall()
            for item in following:
                connection.execute(
                    "UPDATE blocks SET position = ? WHERE id = ?",
                    (int(item["position"]) - 1, int(item["id"])),
                )
            self._touch_page(connection, int(row["page_id"]))

    def save_blocks(self, document_id: int, blocks: list[Block], *, touch: bool) -> None:
        if not blocks:
            return
        with self.transaction() as connection:
            for block in blocks:
                if block.id is None:
                    raise StorageError("Bloco sem identificador.")
                alignment = self._validate_alignment(block.alignment)
                font_size = self._validate_font_size(block.font_size)
                role = self._validate_role(block.role)
                updated = connection.execute(
                    """
                    UPDATE blocks
                    SET html = ?, alignment = ?, font_size = ?, role = ?, position = ?
                    WHERE id = ?
                      AND page_id IN (SELECT id FROM pages WHERE document_id = ?)
                    """,
                    (block.html, alignment, font_size, role, block.position, block.id, document_id),
                )
                if updated.rowcount != 1:
                    raise StorageError("Não foi possível salvar um bloco deste documento.")
            if touch:
                connection.execute(
                    "UPDATE documents SET updated_at = ? WHERE id = ?",
                    (timestamp(), document_id),
                )

    def replace_document_content(self, document: Document) -> None:
        """Substitui páginas e blocos. Usado na importação de um documento novo."""
        if document.id is None:
            raise StorageError("Documento sem identificador.")
        with self.transaction() as connection:
            connection.execute("DELETE FROM pages WHERE document_id = ?", (document.id,))
            for position, page in enumerate(document.pages):
                blocks = normalize_blocks(page.blocks)
                self._insert_page(connection, document.id, position, blocks)
            connection.execute(
                """
                UPDATE documents
                SET current_page_index = ?, updated_at = ?
                WHERE id = ?
                """,
                (clamp_index(document.current_page_index, len(document.pages)), timestamp(), document.id),
            )

    def get_state(self, key: str, default: str | None = None) -> str | None:
        return self._read_state(self.connection, key, default)

    def set_state(self, key: str, value: str) -> None:
        with self.transaction() as connection:
            self._write_state(connection, key, value)

    def import_pages(self, name: str, pages: list[Page], *, current_page_index: int = 0,
                     created_at: str | None = None) -> Document:
        cleaned = name.strip() or self.unique_default_name("Importado")
        self._validate_name(cleaned)
        if not pages:
            pages = [Page(position=0, blocks=default_blocks())]
        now = timestamp()
        created = created_at or now
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents (name, created_at, updated_at, current_page_index)
                VALUES (?, ?, ?, ?)
                """,
                (cleaned, created, now, 0),
            )
            document_id = int(cursor.lastrowid)
            for position, page in enumerate(pages):
                self._insert_page(connection, document_id, position, normalize_blocks(page.blocks))
            safe_index = clamp_index(current_page_index, len(pages))
            connection.execute(
                "UPDATE documents SET current_page_index = ? WHERE id = ?",
                (safe_index, document_id),
            )
            self._write_state(connection, "last_document_id", str(document_id))
        return self.load_document(document_id)

    def _load_pages(self, document_id: int) -> list[Page]:
        rows = self.connection.execute(
            "SELECT * FROM pages WHERE document_id = ? ORDER BY position ASC",
            (document_id,),
        ).fetchall()
        pages: list[Page] = []
        for row in rows:
            block_rows = self.connection.execute(
                "SELECT * FROM blocks WHERE page_id = ? ORDER BY position ASC",
                (row["id"],),
            ).fetchall()
            blocks = [
                Block(
                    id=int(item["id"]),
                    role=item["role"],
                    html=item["html"],
                    alignment=item["alignment"],
                    font_size=int(item["font_size"]),
                    position=int(item["position"]),
                )
                for item in block_rows
            ]
            pages.append(Page(id=int(row["id"]), position=int(row["position"]), blocks=blocks))
        if not pages:
            raise StorageError("O documento não possui páginas.")
        return pages

    def _insert_page(
        self,
        connection: sqlite3.Connection,
        document_id: int,
        position: int,
        blocks: list[Block],
    ) -> int:
        cursor = connection.execute(
            "INSERT INTO pages (document_id, position) VALUES (?, ?)",
            (document_id, position),
        )
        page_id = int(cursor.lastrowid)
        prepared = normalize_blocks(blocks)
        for index, block in enumerate(prepared):
            connection.execute(
                """
                INSERT INTO blocks (page_id, position, role, html, alignment, font_size)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    page_id,
                    index,
                    self._validate_role(block.role),
                    block.html or "",
                    self._validate_alignment(block.alignment),
                    self._validate_font_size(block.font_size),
                ),
            )
        return page_id

    def _shift_pages_up(self, connection: sqlite3.Connection, document_id: int, position: int) -> None:
        rows = connection.execute(
            """
            SELECT id, position FROM pages
            WHERE document_id = ? AND position >= ?
            ORDER BY position DESC
            """,
            (document_id, position),
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE pages SET position = ? WHERE id = ?",
                (-int(row["position"]) - 1, int(row["id"])),
            )
        for row in rows:
            connection.execute(
                "UPDATE pages SET position = ? WHERE id = ?",
                (int(row["position"]) + 1, int(row["id"])),
            )

    def _shift_pages_down(self, connection: sqlite3.Connection, document_id: int, position: int) -> None:
        rows = connection.execute(
            """
            SELECT id, position FROM pages
            WHERE document_id = ? AND position > ?
            ORDER BY position ASC
            """,
            (document_id, position),
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE pages SET position = ? WHERE id = ?",
                (int(row["position"]) - 1, int(row["id"])),
            )

    def _next_block_position(self, connection: sqlite3.Connection, page_id: int) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM blocks WHERE page_id = ?",
            (page_id,),
        ).fetchone()
        if row is None:
            raise StorageError("Página não encontrada.")
        return int(row["next_pos"])

    def _touch_page(self, connection: sqlite3.Connection, page_id: int) -> None:
        connection.execute(
            """
            UPDATE documents
            SET updated_at = ?
            WHERE id = (SELECT document_id FROM pages WHERE id = ?)
            """,
            (timestamp(), page_id),
        )

    def _read_state(
        self,
        connection: sqlite3.Connection,
        key: str,
        default: str | None = None,
    ) -> str | None:
        row = connection.execute(
            "SELECT value FROM app_state WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["value"])

    def _write_state(self, connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            """
            INSERT INTO app_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    @staticmethod
    def _validate_name(name: str) -> None:
        if not name.strip():
            raise StorageError("O documento precisa de um nome.")
        if len(name.strip()) > 200:
            raise StorageError("O nome pode ter no máximo 200 caracteres.")

    @staticmethod
    def _validate_alignment(value: str) -> str:
        if value not in ALIGNMENTS:
            raise StorageError(f"Alinhamento inválido: {value}")
        return value

    @staticmethod
    def _validate_role(value: str) -> str:
        if value not in ROLES:
            raise StorageError(f"Tipo de bloco inválido: {value}")
        return value

    @staticmethod
    def _validate_font_size(value: int) -> int:
        size = int(value)
        if size < MIN_FONT_SIZE or size > MAX_FONT_SIZE:
            raise StorageError("Tamanho de fonte inválido.")
        return size
