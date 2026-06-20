"""Centralised application settings, backed by QSettings.

On Windows QSettings persists to HKCU\\Software\\QtProcMan — so preferences
(theme, refresh interval, window geometry) survive across runs.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

from .theme import DEFAULT_THEME, THEMES

_ORG = "QtProcMan"
_APP = "QtProcMan"

DEFAULT_INTERVAL_MS = 1000
# (label, milliseconds) — offered in the Settings dialog.
INTERVAL_CHOICES: list[tuple[str, int]] = [
    ("0.5 seconds", 500),
    ("1 second", 1000),
    ("2 seconds", 2000),
    ("5 seconds", 5000),
    ("10 seconds", 10000),
]


class AppSettings:
    def __init__(self):
        self._s = QSettings(_ORG, _APP)

    # ── theme ──────────────────────────────────────────────────────────────────
    def theme(self) -> str:
        value = self._s.value("theme", DEFAULT_THEME)
        return value if value in THEMES else DEFAULT_THEME

    def set_theme(self, name: str) -> None:
        self._s.setValue("theme", name)

    # ── refresh interval ───────────────────────────────────────────────────────
    def interval_ms(self, default: int = DEFAULT_INTERVAL_MS) -> int:
        try:
            value = int(self._s.value("interval_ms", default))
        except (TypeError, ValueError):
            return default
        return value if value >= 200 else default

    def set_interval_ms(self, ms: int) -> None:
        self._s.setValue("interval_ms", int(ms))

    # ── window geometry ────────────────────────────────────────────────────────
    def geometry(self):
        return self._s.value("geometry")  # QByteArray or None

    def set_geometry(self, data) -> None:
        self._s.setValue("geometry", data)

    # ── persistence ────────────────────────────────────────────────────────────
    def sync(self) -> None:
        self._s.sync()
