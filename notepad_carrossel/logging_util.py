"""Registro local de falhas, ao lado dos dados do usuário."""

from __future__ import annotations

import traceback
from datetime import datetime

from notepad_carrossel.paths import StorageLayout


def log_exception(layout: StorageLayout, message: str, exc: BaseException | None = None) -> None:
    try:
        layout.data_dir.mkdir(parents=True, exist_ok=True)
        with layout.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
            if exc is not None:
                handle.write("".join(traceback.format_exception(exc)))
            else:
                handle.write(traceback.format_exc())
            handle.write("\n")
    except OSError:
        return
