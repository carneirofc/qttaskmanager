"""Generic table model for the scan tabs.

On-demand scans return a complete result set at once, so this model uses a
full reset on load() (no diffing needed, unlike ProcessModel). Columns are
declared declaratively via ColumnSpec; a single 'severity' field per row drives
the foreground colour of the column marked colored=True.
"""
from __future__ import annotations

from typing import NamedTuple

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

from .proc_model import AnyColumnFilter

# Custom role so numeric columns sort numerically while the proxy still filters
# against DisplayRole text.
SORT_ROLE = Qt.UserRole + 1

_SEVERITY_COLOR: dict[str, QColor] = {
    "ok":     QColor("#3fae3f"),
    "review": QColor("#f0a000"),
    "warn":   QColor("#e0913a"),
    "broken": QColor("#e0584f"),
    "info":   QColor("#5aafff"),
}
_DEFAULT_FG = QColor("#cccccc")

_ALIGN_RIGHT = Qt.AlignRight | Qt.AlignVCenter


class ColumnSpec(NamedTuple):
    header: str
    key: str
    align: str = "L"            # "L" or "R"
    tooltip: str = ""
    colored: bool = False       # tint this column by the row's severity
    sort_key: str | None = None  # dict key to sort by (defaults to `key`)
    width: int = 0              # initial pixel width (0 = leave default)


class ScanTableModel(QAbstractTableModel):
    def __init__(self, columns: list[ColumnSpec], parent=None):
        super().__init__(parent)
        self._columns = columns
        self._rows: list[dict] = []

    # ── QAbstractTableModel interface ─────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        spec = self._columns[section]
        if role == Qt.DisplayRole:
            return spec.header
        if role == Qt.ToolTipRole:
            return spec.tooltip or None
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        spec = self._columns[index.column()]
        val = row.get(spec.key, "")

        if role == Qt.DisplayRole:
            return str(val)

        if role == SORT_ROLE:
            sv = row.get(spec.sort_key or spec.key, "")
            return sv if isinstance(sv, (int, float)) else str(sv).lower()

        if role == Qt.ForegroundRole and spec.colored:
            return _SEVERITY_COLOR.get(row.get("severity", ""), _DEFAULT_FG)

        if role == Qt.TextAlignmentRole and spec.align == "R":
            return _ALIGN_RIGHT

        if role == Qt.ToolTipRole:
            return str(val) or None

        return None

    # ── load (full reset) ─────────────────────────────────────────────────────

    def load(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_at(self, row: int) -> dict | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None


class ScanFilter(AnyColumnFilter):
    """All-column text filter that sorts via SORT_ROLE (numeric-aware)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
