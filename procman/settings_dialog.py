"""Settings (Preferences) dialog — edit theme and refresh interval."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLabel, QDialogButtonBox,
)

from .theme import THEMES
from .settings import AppSettings, INTERVAL_CHOICES


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)

        self._theme = QComboBox()
        self._theme.addItems(list(THEMES))
        self._theme.setCurrentText(settings.theme())

        self._interval = QComboBox()
        for label, ms in INTERVAL_CHOICES:
            self._interval.addItem(label, ms)
        current = settings.interval_ms()
        idx = next((i for i, (_l, ms) in enumerate(INTERVAL_CHOICES) if ms == current), -1)
        if idx < 0:                                  # custom value not in the list
            self._interval.addItem(f"{current} ms", current)
            idx = self._interval.count() - 1
        self._interval.setCurrentIndex(idx)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow("Theme", self._theme)
        form.addRow("Refresh interval", self._interval)

        hint = QLabel("Settings are saved to your user profile and restored on next launch.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(12)
        root.addLayout(form)
        root.addWidget(hint)
        root.addWidget(buttons)

    def selected_theme(self) -> str:
        return self._theme.currentText()

    def selected_interval_ms(self) -> int:
        return int(self._interval.currentData())
