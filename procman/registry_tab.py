"""Registry tab — an application registry explorer plus a broken-entry scan.

`RegistryTab` hosts two sub-tabs: an Explorer (browse application registry keys)
and Issues (scan for entries whose target is missing). Both are read-only.
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMenu, QApplication

from .scan_tab import ScanTab
from .scan_model import ColumnSpec
from .registry_data import scan_registry
from .registry_explorer import RegistryExplorer


class RegistryScanTab(ScanTab):
    def columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec("Category", "category", width=120, tooltip="Kind of registry entry"),
            ColumnSpec("Hive",     "hive",     width=120, tooltip="Registry root / view"),
            ColumnSpec("Name",     "name",     width=240, tooltip="Value or application name"),
            ColumnSpec("Issue",    "issue",    colored=True, width=230,
                       tooltip="Why this entry is flagged"),
            ColumnSpec("Target",   "target",   tooltip="Path the entry points to"),  # stretches
        ]

    def scan_callable(self):
        return scan_registry

    def banner_text(self) -> str:
        return ("🛈  Read-only scan — no registry keys are modified. Flags startup, "
                "App Paths and uninstall entries whose target is gone. Removal is "
                "not implemented (TODO) — edit with regedit at your own risk.")

    def scan_label(self) -> str:
        return "Scan registry"

    def action_label(self) -> str | None:
        return "Remove entries…"

    def path_key(self) -> str | None:
        return "target"

    def empty_hint(self) -> str:
        return "No broken registry entries found."

    def summary_text(self, rows: list[dict]) -> str:
        return f"{len(rows)} potential issue(s) found"

    def add_extra_actions(self, menu: QMenu, row: dict) -> None:
        keypath = row.get("keypath")
        if keypath:
            act = QAction("Copy registry key", self)
            act.triggered.connect(lambda: QApplication.clipboard().setText(keypath))
            menu.addAction(act)


class RegistryTab(QWidget):
    """Registry tab: an Explorer sub-tab + an Issues (broken-entry scan) sub-tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._explorer = RegistryExplorer()
        self._issues = RegistryScanTab()

        self._inner = QTabWidget()
        self._inner.addTab(self._explorer, "Explorer")
        self._inner.addTab(self._issues, "Issues")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._inner)

    # Delegated so the Tools menu / Run-all-scans and window shutdown keep working.
    def run_scan(self) -> None:
        self._inner.setCurrentWidget(self._issues)
        self._issues.run_scan()

    def shutdown(self) -> None:
        self._issues.shutdown()
