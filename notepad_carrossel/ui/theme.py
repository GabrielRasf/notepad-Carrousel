"""Aparência escura para uso prolongado, com a página em tom de papel."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

STYLESHEET = """
QMainWindow, QWidget#root {
    background: #14161a;
    color: #f3efe9;
    font-family: "Segoe UI", sans-serif;
    font-size: 14px;
}
QMenuBar {
    background: #14161a;
    color: #f3efe9;
    border-bottom: 1px solid #2a2e36;
    padding: 2px 6px;
}
QMenuBar::item {
    padding: 6px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #3a2c32;
}
QMenu {
    background: #22262e;
    color: #f3efe9;
    border: 1px solid #343a46;
    padding: 6px;
}
QMenu::item {
    padding: 7px 22px;
    border-radius: 6px;
}
QFrame#header {
    background: #14161a;
    border-bottom: 1px solid #2a2e36;
}
QLabel#appTitle, QLabel#docTitle {
    color: #f7f4ef;
    font-size: 18px;
    font-weight: 600;
}
QLabel#pageIndicator {
    color: #f7f4ef;
    font-size: 18px;
    font-weight: 650;
    padding: 0 12px;
}
QLabel#hintLabel, QLabel#pathLabel, QLabel#metaLabel {
    color: #a39b92;
    font-size: 12px;
}
QLabel#saveOk { color: #7ddec0; font-weight: 600; }
QLabel#savePending { color: #e6c56e; font-weight: 600; }
QLabel#saveError { color: #ff9d96; font-weight: 600; }
QFrame#pageCard {
    background: #fbf7f2;
    border: 1px solid #e5ddd3;
    border-radius: 18px;
}
QFrame#pageCard QLabel#roleLabel {
    color: #8d8278;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
}
QFrame#pageCard QTextEdit {
    background: transparent;
    color: #1f1a17;
    border: none;
    selection-background-color: #e7c3b6;
    selection-color: #1f1a17;
    padding: 2px 4px;
}
QFrame#pageCard QTextEdit:focus {
    background: rgba(196, 101, 74, 0.08);
    border-radius: 8px;
}
QScrollArea#pageScroll {
    background: transparent;
    border: none;
}
QWidget#pageContent {
    background: #fbf7f2;
}
QPushButton#arrowButton {
    background: #232830;
    color: #f7f4ef;
    border: 1px solid #3a4150;
    border-radius: 28px;
    font-size: 30px;
    min-width: 56px;
    max-width: 56px;
    min-height: 56px;
    max-height: 56px;
}
QPushButton#arrowButton:hover {
    background: #c4654a;
    border-color: #c4654a;
}
QPushButton#arrowButton:disabled {
    color: #555d6a;
    background: #1b1f26;
    border-color: #2a3038;
}
QPushButton, QToolButton {
    background: #2a303a;
    color: #f3efe9;
    border: 1px solid #3a4150;
    border-radius: 8px;
    padding: 6px 12px;
}
QPushButton:hover, QToolButton:hover {
    background: #353c48;
}
QPushButton:disabled, QToolButton:disabled {
    color: #6d7480;
    background: #1d2128;
}
QPushButton#primary {
    background: #c4654a;
    border-color: #c4654a;
    color: white;
    font-weight: 600;
}
QPushButton#primary:hover { background: #d4785c; }
QPushButton#quiet {
    background: transparent;
    border: none;
    color: #d9d3cb;
    font-size: 16px;
    font-weight: 600;
    padding: 4px 8px;
}
QPushButton#quiet:hover { color: white; }
QPushButton#danger:hover {
    background: #8d3d38;
    border-color: #8d3d38;
}
QToolButton:checked {
    background: #c4654a;
    border-color: #c4654a;
    color: white;
}
QToolBar {
    background: #191c21;
    border: none;
    border-bottom: 1px solid #2a2e36;
    spacing: 4px;
    padding: 6px 10px;
}
QToolBar QToolButton {
    min-width: 34px;
    padding: 5px 8px;
}
QLineEdit, QSpinBox, QComboBox {
    background: #1c2026;
    color: #f3efe9;
    border: 1px solid #3a4150;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 22px;
}
QSpinBox { min-width: 72px; }
QListWidget {
    background: #1b1e24;
    color: #f3efe9;
    border: 1px solid #2e343e;
    border-radius: 12px;
    padding: 6px;
    outline: none;
}
QListWidget::item {
    padding: 10px 12px;
    border-radius: 8px;
}
QListWidget::item:selected {
    background: #4a332f;
    color: #fff8f4;
}
QStatusBar {
    background: #101216;
    color: #b7b1a8;
}
QPushButton:focus, QToolButton:focus, QListWidget:focus, QLineEdit:focus, QSpinBox:focus {
    border-color: #e0b2a4;
}
"""


def apply_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#14161a"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f3efe9"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1c2026"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#22262e"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f3efe9"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2a303a"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f3efe9"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#c4654a"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#22262e"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f3efe9"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8e877e"))
    app.setPalette(palette)
