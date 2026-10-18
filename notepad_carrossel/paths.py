"""Pastas portáteis do Notepad Carrossel.

Os documentos ficam ao lado do executável. O diretório de trabalho e a pasta
temporária do PyInstaller nunca são usados como armazenamento.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

STORAGE_POINTER_NAME = "storage_location.txt"
DATABASE_NAME = "notepad.sqlite"
USER_POINTER_DIRNAME = "NotepadCarrossel"


@dataclass(frozen=True)
class StorageLayout:
    root: Path
    data_dir: Path
    backup_dir: Path
    database_path: Path
    log_path: Path
    pointer_file: Path
    using_fallback: bool
    app_dir: Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path | None:
    """Pasta temporária do PyInstaller. Dados do usuário nunca devem ir para cá."""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    return Path(meipass).resolve()


def application_dir(executable: Path | None = None) -> Path:
    """Diretório do executável, ou a raiz do projeto quando roda pelo código."""
    if executable is not None:
        return executable.resolve().parent
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_settings_pointer() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / USER_POINTER_DIRNAME / STORAGE_POINTER_NAME


def is_writable_dir(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def is_inside(path: Path, parent: Path | None) -> bool:
    if parent is None:
        return False
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError):
        return False
    return True


def read_pointer(pointer_file: Path) -> Path | None:
    try:
        if not pointer_file.is_file():
            return None
        for raw in pointer_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip().lstrip("\ufeff")
            if line and not line.startswith("#"):
                return Path(line)
    except OSError:
        return None
    return None


def write_pointer(pointer_file: Path, root: Path) -> None:
    pointer_file.parent.mkdir(parents=True, exist_ok=True)
    pointer_file.write_text(str(root.resolve()) + "\n", encoding="utf-8")


def _layout(root: Path, *, app_dir: Path, using_fallback: bool) -> StorageLayout:
    data_dir = root / "data"
    backup_dir = root / "backup"
    return StorageLayout(
        root=root,
        data_dir=data_dir,
        backup_dir=backup_dir,
        database_path=data_dir / DATABASE_NAME,
        log_path=data_dir / "app.log",
        pointer_file=app_dir / STORAGE_POINTER_NAME,
        using_fallback=using_fallback,
        app_dir=app_dir,
    )


def _usable(root: Path, temp_root: Path | None) -> bool:
    try:
        resolved = root.resolve()
    except OSError:
        return False
    if is_inside(resolved, temp_root):
        return False
    layout = _layout(resolved, app_dir=resolved, using_fallback=False)
    return is_writable_dir(layout.data_dir) and is_writable_dir(layout.backup_dir)


def resolve_storage(
    *,
    executable: Path | None = None,
    meipass: Path | None = None,
    preferred_fallback: Path | None = None,
    allow_user_settings: bool = True,
) -> tuple[StorageLayout | None, str | None]:
    """Escolhe a pasta de dados.

    A preferência é a pasta do executável. Um ponteiro só entra em cena quando
    o usuário já escolheu outro local, ou quando a pasta do programa não aceita
    gravação. Retorna (None, mensagem) se for preciso perguntar ao usuário.
    """
    app_dir = application_dir(executable).resolve()
    temp_root = meipass.resolve() if meipass is not None else bundle_dir()
    if temp_root is not None:
        temp_root = temp_root.resolve()

    pointer_targets: list[Path] = []
    local_pointer = read_pointer(app_dir / STORAGE_POINTER_NAME)
    if local_pointer is not None:
        pointer_targets.append(local_pointer)
    if allow_user_settings:
        settings_pointer = read_pointer(user_settings_pointer())
        if settings_pointer is not None:
            pointer_targets.append(settings_pointer)

    for target in pointer_targets:
        if _usable(target, temp_root):
            resolved = target.resolve()
            return _layout(resolved, app_dir=app_dir, using_fallback=resolved != app_dir), None

    if _usable(app_dir, temp_root):
        return _layout(app_dir, app_dir=app_dir, using_fallback=False), None

    if preferred_fallback is not None and _usable(preferred_fallback, temp_root):
        resolved = preferred_fallback.resolve()
        return _layout(resolved, app_dir=app_dir, using_fallback=True), None

    return None, (
        f"Não foi possível gravar em:\n{app_dir}\\data\n\n"
        "Escolha outra pasta. Os documentos serão guardados em data\\ e backup\\ dentro dela."
    )


def ensure_layout(layout: StorageLayout) -> None:
    layout.data_dir.mkdir(parents=True, exist_ok=True)
    layout.backup_dir.mkdir(parents=True, exist_ok=True)


def remember_choice(
    app_dir: Path,
    chosen_root: Path,
    *,
    user_pointer: Path | None = None,
) -> Path:
    """Lembra a pasta escolhida. Se a pasta do programa for só leitura, usa o perfil."""
    pointer = app_dir / STORAGE_POINTER_NAME
    try:
        write_pointer(pointer, chosen_root)
        return pointer
    except OSError:
        target = user_pointer or user_settings_pointer()
        write_pointer(target, chosen_root)
        return target
