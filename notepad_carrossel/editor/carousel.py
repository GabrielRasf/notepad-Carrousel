"""Troca de página com um esmaecimento curto."""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class FadeHost(QWidget):
    """Mostra um widget por vez e esmaece a página nova por cima da anterior."""

    def __init__(self):
        super().__init__()
        self.setObjectName("slideHost")
        self.setMinimumSize(420, 360)
        self._current: QWidget | None = None
        self._anim: QPropertyAnimation | None = None
        self._token = 0

    def show_widget(self, widget: QWidget, *, animated: bool) -> None:
        self._token += 1
        token = self._token
        self._stop_animation()
        if self._current is not None:
            self._current.setGraphicsEffect(None)
        widget.setParent(self)
        widget.setGeometry(self.rect())

        if not animated or self._current is None or self._current is widget:
            self._discard_except(widget)
            widget.setGraphicsEffect(None)
            widget.show()
            widget.raise_()
            self._current = widget
            return

        previous = self._current
        self._discard_except_many({previous, widget})
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        widget.show()
        widget.raise_()
        self._current = widget

        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(240)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.finished.connect(
            lambda token=token, widget=widget, previous=previous: self._finish(token, widget, previous)
        )
        self._anim = animation
        animation.start()

    def resizeEvent(self, event) -> None:  # noqa: N802 - API do Qt
        super().resizeEvent(event)
        rect = self.rect()
        for child in self.children():
            if isinstance(child, QWidget):
                child.setGeometry(rect)

    def _finish(self, token: int, widget: QWidget, previous: QWidget | None) -> None:
        if token != self._token:
            return
        widget.setGraphicsEffect(None)
        if previous is not None and previous is not widget:
            previous.hide()
            previous.setParent(None)
            previous.deleteLater()
        self._anim = None

    def _stop_animation(self) -> None:
        if self._anim is None:
            return
        animation = self._anim
        self._anim = None
        if animation.state() == QAbstractAnimation.State.Running:
            animation.stop()
        animation.deleteLater()

    def _discard_except(self, keep: QWidget | None) -> None:
        self._discard_except_many({keep} if keep is not None else set())

    def _discard_except_many(self, keep: set[QWidget]) -> None:
        for child in list(self.children()):
            if isinstance(child, QWidget) and child not in keep:
                child.hide()
                child.setParent(None)
                child.deleteLater()
