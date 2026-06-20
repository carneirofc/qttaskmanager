"""Application registry explorer (READ-ONLY).

A lazily-populated tree of the registry locations where Windows records
applications — installed-app uninstall keys, App Paths, startup (Run) keys and
Classes\\Applications — with a values panel for the selected key. Values that
point at a missing executable are highlighted. Nothing is ever written.
"""
from __future__ import annotations

import os
import winreg

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QLabel, QMenu, QApplication,
)

from . import registry_util as reg
from .scan_model import ScanTableModel, ScanFilter, ColumnSpec
from .scan_data import expand, extract_exe, path_missing
from .widgets import make_table
from .detail_dialog import open_file_location

_ROLE = Qt.UserRole          # stores (root, subkey, view) on each tree item
_HKCU = winreg.HKEY_CURRENT_USER
_HKLM = winreg.HKEY_LOCAL_MACHINE
_W64 = winreg.KEY_WOW64_64KEY
_W32 = winreg.KEY_WOW64_32KEY

_UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
_APP_PATHS = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
_RUN       = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUNONCE   = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
_CLASSES_APPS = r"Software\Classes\Applications"

# Top-level entry points into the registry (label, root, subkey, view).
_CATEGORIES = [
    ("Installed Apps — HKLM (64-bit)", _HKLM, _UNINSTALL, _W64),
    ("Installed Apps — HKLM (32-bit)", _HKLM, _UNINSTALL, _W32),
    ("Installed Apps — HKCU",          _HKCU, _UNINSTALL, 0),
    ("App Paths — HKLM",               _HKLM, _APP_PATHS, _W64),
    ("App Paths — HKCU",               _HKCU, _APP_PATHS, 0),
    ("Startup · Run — HKCU",           _HKCU, _RUN, 0),
    ("Startup · Run — HKLM",           _HKLM, _RUN, _W64),
    ("Startup · RunOnce — HKCU",       _HKCU, _RUNONCE, 0),
    ("Classes · Applications — HKLM",  _HKLM, _CLASSES_APPS, _W64),
]


def _value_severity(value, typ: int) -> str:
    """Flag a value red only when it clearly points at a missing .exe."""
    if isinstance(value, str) and value:
        exe = expand(extract_exe(value))
        if os.path.isabs(exe) and exe.lower().endswith(".exe") and path_missing(exe):
            return "broken"
    return ""


class RegistryExplorer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._populate_roots()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter loaded applications…")
        self._filter.setToolTip("Hide loaded tree entries that don't match (expand a category first)")
        self._filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self._filter)
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Application registry keys"])
        self._tree.setUniformRowHeights(True)
        self._tree.itemExpanded.connect(self._on_expand)
        self._tree.currentItemChanged.connect(self._on_select)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._tree_menu)
        splitter.addWidget(self._tree)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self._sel_label = QLabel("Select a key to view its values")
        self._sel_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._sel_label.setStyleSheet("color: #888; padding: 0 2px;")
        rl.addWidget(self._sel_label)

        value_cols = [
            ColumnSpec("Name", "name", width=220, tooltip="Value name"),
            ColumnSpec("Type", "type", width=120, tooltip="Registry value type"),
            ColumnSpec("Data", "data", colored=True, tooltip="Value data (red = missing target)"),
        ]
        self._values_model = ScanTableModel(value_cols)
        self._values_proxy = ScanFilter()
        self._values_proxy.setSourceModel(self._values_model)
        self._values_table = make_table(self._values_proxy)
        self._values_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._values_table.customContextMenuRequested.connect(self._values_menu)
        vhdr = self._values_table.horizontalHeader()
        for i, spec in enumerate(value_cols):
            if spec.width:
                vhdr.resizeSection(i, spec.width)
        rl.addWidget(self._values_table)
        splitter.addWidget(right)

        splitter.setSizes([430, 720])
        layout.addWidget(splitter)

    # ── tree population (lazy) ─────────────────────────────────────────────────

    def _populate_roots(self) -> None:
        for label, root, subkey, view in _CATEGORIES:
            item = QTreeWidgetItem(self._tree, [label])
            item.setData(0, _ROLE, (root, subkey, view))
            QTreeWidgetItem(item, ["…"])  # placeholder → shows the expand arrow

    def _on_expand(self, item: QTreeWidgetItem) -> None:
        # Populate only the first time (placeholder child has no ROLE data).
        if not (item.childCount() == 1 and item.child(0).data(0, _ROLE) is None):
            return
        item.takeChild(0)
        data = item.data(0, _ROLE)
        if not data:
            return
        root, subkey, view = data
        for name in reg.subkeys(root, subkey, view):
            child_sub = f"{subkey}\\{name}" if subkey else name
            child = QTreeWidgetItem(item, [name])
            child.setData(0, _ROLE, (root, child_sub, view))
            if reg.has_subkeys(root, child_sub, view):
                QTreeWidgetItem(child, ["…"])

    # ── selection → values ─────────────────────────────────────────────────────

    def _on_select(self, current: QTreeWidgetItem, _previous) -> None:
        data = current.data(0, _ROLE) if current else None
        if not data:
            self._values_model.load([])
            self._sel_label.setText("Select a key to view its values")
            return
        root, subkey, view = data
        self._sel_label.setText(f"{reg.HIVE_LABEL.get(root, '')}\\{subkey}")
        rows = [
            {
                "name": name or "(Default)",
                "type": reg.type_name(typ),
                "data": reg.format_value(value, typ),
                "severity": _value_severity(value, typ),
            }
            for name, value, typ in reg.values(root, subkey, view)
        ]
        self._values_model.load(rows)

    # ── filter ──────────────────────────────────────────────────────────────────

    def _apply_filter(self, text: str) -> None:
        needle = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            cat = self._tree.topLevelItem(i)
            for j in range(cat.childCount()):
                child = cat.child(j)
                if child.data(0, _ROLE) is None:
                    continue  # placeholder
                child.setHidden(bool(needle) and needle not in child.text(0).lower())

    # ── context menus (read-only) ──────────────────────────────────────────────

    def _tree_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        data = item.data(0, _ROLE) if item else None
        if not data:
            return
        root, subkey, view = data
        path = f"{reg.HIVE_LABEL.get(root, '')}\\{subkey}"
        menu = QMenu(self)
        act = QAction("Copy registry key path", self)
        act.triggered.connect(lambda: QApplication.clipboard().setText(path))
        menu.addAction(act)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _values_menu(self, pos) -> None:
        idx = self._values_table.indexAt(pos)
        if not idx.isValid():
            return
        row = self._values_model.row_at(self._values_proxy.mapToSource(idx).row())
        if not row:
            return
        menu = QMenu(self)
        act_copy = QAction("Copy value", self)
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(row.get("data", "")))
        menu.addAction(act_copy)

        exe = expand(extract_exe(row.get("data", "")))
        if exe and os.path.isabs(exe) and os.path.exists(exe):
            act_open = QAction("Open target in Explorer", self)
            act_open.triggered.connect(lambda: open_file_location(exe))
            menu.addAction(act_open)
        menu.exec(self._values_table.viewport().mapToGlobal(pos))
