"""A pasta de dados acompanha o executável e aceita acentos."""

from __future__ import annotations

from pathlib import Path

from notepad_carrossel.paths import (
    application_dir,
    is_inside,
    remember_choice,
    resolve_storage,
    write_pointer,
)
from notepad_carrossel.storage.database import Database


def test_application_dir_ignores_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert application_dir() == Path(__file__).resolve().parents[1]


def test_storage_uses_executable_dir_not_cwd_or_meipass(tmp_path, monkeypatch):
    meipass = tmp_path / "Temp" / "_MEI12345"
    meipass.mkdir(parents=True)
    app_dir = tmp_path / "área de trabalho" / "Notepad Carrossel"
    app_dir.mkdir(parents=True)
    cwd = tmp_path / "outro lugar"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    layout, error = resolve_storage(
        executable=app_dir / "NotepadCarrossel.exe",
        meipass=meipass,
        allow_user_settings=False,
    )
    assert error is None
    assert layout is not None
    assert layout.data_dir == (app_dir / "data").resolve()
    assert layout.database_path.parent == layout.data_dir
    assert not is_inside(layout.database_path, meipass)
    assert not is_inside(layout.database_path, cwd)
    assert not layout.using_fallback

    database = Database(layout.database_path)
    document = database.create_document("Caminho acentuado")
    database.close()
    assert document.id is not None
    assert layout.database_path.is_file()


def test_meipass_is_never_a_storage_root(tmp_path):
    meipass = tmp_path / "_MEI999"
    meipass.mkdir()
    layout, error = resolve_storage(
        executable=meipass / "NotepadCarrossel.exe",
        meipass=meipass,
        allow_user_settings=False,
    )
    assert layout is None
    assert error


def test_pointer_and_fallback_when_app_dir_is_not_writable(tmp_path, monkeypatch):
    app_dir = tmp_path / "Program Files" / "Notepad Carrossel"
    app_dir.mkdir(parents=True)
    fallback = tmp_path / "área alternativa"
    real = __import__("notepad_carrossel.paths", fromlist=["is_writable_dir"]).is_writable_dir

    def fake(directory: Path) -> bool:
        try:
            resolved = directory.resolve()
        except OSError:
            return False
        if resolved == app_dir.resolve() or app_dir.resolve() in resolved.parents:
            return False
        return real(directory)

    monkeypatch.setattr("notepad_carrossel.paths.is_writable_dir", fake)
    layout, error = resolve_storage(
        executable=app_dir / "NotepadCarrossel.exe",
        preferred_fallback=fallback,
        allow_user_settings=False,
    )
    assert error is None
    assert layout is not None
    assert layout.using_fallback
    assert layout.root == fallback.resolve()
    assert (fallback / "data").is_dir()
    assert (fallback / "backup").is_dir()


def test_saved_pointer_is_reused(tmp_path):
    app_dir = tmp_path / "app"
    other = tmp_path / "outro lugar"
    app_dir.mkdir()
    write_pointer(app_dir / "storage_location.txt", other)
    layout, error = resolve_storage(
        executable=app_dir / "NotepadCarrossel.exe",
        allow_user_settings=False,
    )
    assert error is None
    assert layout is not None
    assert layout.root == other.resolve()
    assert layout.using_fallback

    remembered = remember_choice(app_dir, other)
    assert remembered == app_dir / "storage_location.txt"
    assert other.resolve().as_posix() in remembered.read_text(encoding="utf-8").replace("\\", "/") or str(
        other.resolve()
    ) in remembered.read_text(encoding="utf-8")
