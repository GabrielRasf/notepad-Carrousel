"""Cópias de segurança e restauração do banco local."""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from notepad_carrossel.storage.database import Database, StorageError, file_integrity_ok


class BackupManager:
    """Cria, confere e restaura cópias sem substituir um backup válido por lixo."""

    def __init__(self, backup_dir: Path):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create(self, database: Database, *, kind: str = "manual") -> Path:
        if kind not in {"manual", "auto", "safety"}:
            raise StorageError("Tipo de backup desconhecido.")
        if not database.integrity_ok():
            raise StorageError(
                "O banco atual não passou na verificação de integridade. "
                "Nenhuma cópia foi substituída."
            )
        destination = self._unique_path(kind)
        target = sqlite3.connect(destination)
        try:
            database.connection.backup(target)
        except sqlite3.Error as exc:
            target.close()
            destination.unlink(missing_ok=True)
            raise StorageError(f"Não foi possível criar a cópia de segurança: {exc}") from exc
        else:
            target.close()
        if not file_integrity_ok(destination):
            destination.unlink(missing_ok=True)
            raise StorageError(
                "A cópia gerada falhou na verificação e foi descartada. "
                "Os backups anteriores foram mantidos."
            )
        self.prune(kind)
        return destination

    def prune(self, kind: str, *, keep: int = 15) -> None:
        files = self._files(kind)
        valid = [path for path in files if file_integrity_ok(path)]
        invalid = [path for path in files if path not in valid]
        for path in invalid:
            path.unlink(missing_ok=True)
        # Nunca apaga a última cópia válida, mesmo que o limite seja menor.
        removable = valid[keep:] if len(valid) > 1 else []
        protected = set(valid[:keep])
        for path in removable:
            if path not in protected:
                path.unlink(missing_ok=True)

    def latest_valid(self) -> Path | None:
        candidates: list[Path] = []
        for kind in ("manual", "safety", "auto"):
            candidates.extend(self._files(kind))
        valid = [path for path in candidates if file_integrity_ok(path)]
        if not valid:
            return None
        valid.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return valid[0]

    def list_backups(self) -> list[Path]:
        files: list[Path] = []
        for kind in ("manual", "safety", "auto"):
            files.extend(self._files(kind))
        return [path for path in files if file_integrity_ok(path)]

    def install(self, backup_path: Path, database_path: Path) -> None:
        """Copia um backup válido para o caminho do banco, sem alterar a origem."""
        source = Path(backup_path)
        if not file_integrity_ok(source):
            raise StorageError(
                "A cópia selecionada está incompleta ou corrompida e não foi restaurada."
            )
        destination = Path(database_path)
        temporary = destination.with_name(destination.name + ".restore.tmp")
        temporary.unlink(missing_ok=True)
        self._copy_sqlite(source, temporary)
        if not file_integrity_ok(temporary):
            temporary.unlink(missing_ok=True)
            raise StorageError("A restauração foi cancelada porque o arquivo gerado falhou na verificação.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._remove_sidecars(destination)
        try:
            os.replace(temporary, destination)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError(f"Não foi possível gravar o banco restaurado: {exc}") from exc

    def restore(self, backup_path: Path, database: Database) -> None:
        source = Path(backup_path)
        if not file_integrity_ok(source):
            raise StorageError(
                "A cópia selecionada está incompleta ou corrompida e não foi restaurada."
            )
        if database.path.exists() and file_integrity_ok(database.path):
            self.create(database, kind="safety")

        database.close()
        try:
            self.install(source, database.path)
        except StorageError:
            database.reopen()
            raise
        database.reopen()
        if not database.integrity_ok():
            raise StorageError("O banco restaurado não passou na verificação.")

    @staticmethod
    def _copy_sqlite(source: Path, destination: Path) -> None:
        src = sqlite3.connect(source)
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        except sqlite3.Error as exc:
            raise StorageError(f"Falha ao ler a cópia de segurança: {exc}") from exc
        finally:
            dst.close()
            src.close()

    def quarantine(self, database_path: Path) -> Path:
        """Move um banco inválido para backup/quarantine sem apagar cópias boas."""
        quarantine_dir = self.backup_dir / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = quarantine_dir / f"quarantine-{stamp}.sqlite"
        if database_path.exists():
            shutil.move(str(database_path), str(destination))
        self._remove_sidecars(database_path)
        return destination

    def _files(self, kind: str) -> list[Path]:
        files = list(self.backup_dir.glob(f"{kind}-*.sqlite"))
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return files

    def _unique_path(self, kind: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        candidate = self.backup_dir / f"{kind}-{stamp}.sqlite"
        counter = 1
        while candidate.exists():
            candidate = self.backup_dir / f"{kind}-{stamp}-{counter}.sqlite"
            counter += 1
        return candidate

    @staticmethod
    def _remove_sidecars(database_path: Path) -> None:
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database_path) + suffix)
            for _attempt in range(10):
                try:
                    sidecar.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.05)
            else:
                if sidecar.exists():
                    raise StorageError(
                        "Não foi possível liberar um arquivo temporário do banco. "
                        "Feche outras janelas do Notepad Carrossel e tente de novo."
                    )
