"""Modelos de documento, página e bloco."""

from __future__ import annotations

from dataclasses import dataclass, field


ALIGNMENTS = ("left", "center", "right", "justify")
ROLES = ("title", "subtitle", "body", "extra")

# Papel, alinhamento e tamanho de fonte dos blocos criados com cada página.
DEFAULT_BLOCKS: tuple[tuple[str, str, int], ...] = (
    ("title", "center", 28),
    ("subtitle", "left", 18),
    ("body", "justify", 15),
)

MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 96


@dataclass
class Block:
    role: str
    html: str = ""
    alignment: str = "left"
    font_size: int = 15
    position: int = 0
    id: int | None = None

    def copy(self) -> Block:
        return Block(
            role=self.role,
            html=self.html,
            alignment=self.alignment,
            font_size=self.font_size,
            position=self.position,
            id=None,
        )


@dataclass
class Page:
    position: int
    blocks: list[Block] = field(default_factory=list)
    id: int | None = None

    def copy(self) -> Page:
        return Page(
            position=self.position,
            blocks=[block.copy() for block in self.blocks],
            id=None,
        )


@dataclass
class Document:
    name: str
    created_at: str
    updated_at: str
    current_page_index: int = 0
    pages: list[Page] = field(default_factory=list)
    id: int | None = None


@dataclass(frozen=True)
class DocumentSummary:
    id: int
    name: str
    created_at: str
    updated_at: str
    current_page_index: int
    page_count: int


def default_blocks() -> list[Block]:
    return [
        Block(role=role, alignment=alignment, font_size=size, position=index)
        for index, (role, alignment, size) in enumerate(DEFAULT_BLOCKS)
    ]


def normalize_blocks(blocks: list[Block]) -> list[Block]:
    """Garante título, subtítulo e texto principal, preservando blocos extras."""
    first_by_role: dict[str, Block] = {}
    extras: list[Block] = []
    for block in blocks:
        if block.role == "extra":
            extras.append(block.copy())
        elif block.role in ("title", "subtitle", "body") and block.role not in first_by_role:
            first_by_role[block.role] = block.copy()

    ordered: list[Block] = []
    for role, alignment, size in DEFAULT_BLOCKS:
        existing = first_by_role.get(role)
        if existing is None:
            existing = Block(role=role, alignment=alignment, font_size=size)
        if existing.alignment not in ALIGNMENTS:
            existing.alignment = alignment
        existing.font_size = min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, int(existing.font_size)))
        ordered.append(existing)
    for extra in extras:
        if extra.alignment not in ALIGNMENTS:
            extra.alignment = "left"
        extra.font_size = min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, int(extra.font_size)))
        extra.role = "extra"
        ordered.append(extra)
    for index, block in enumerate(ordered):
        block.position = index
        block.id = None
    return ordered
