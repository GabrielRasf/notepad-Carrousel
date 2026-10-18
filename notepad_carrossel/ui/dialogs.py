"""Diálogos curtos em português."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def ask_confirmation(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    accept: str = "Confirmar",
    reject: str = "Cancelar",
) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    yes = box.button(QMessageBox.StandardButton.Yes)
    no = box.button(QMessageBox.StandardButton.No)
    if yes is not None:
        yes.setText(accept)
    if no is not None:
        no.setText(reject)
    return box.exec() == QMessageBox.StandardButton.Yes
