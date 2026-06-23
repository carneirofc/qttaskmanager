"""Process table model with diff-based updates (no full reset = no scroll jump)."""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QColor

COLS    = ["PID", "Name", "CPU %", "Mem MB", "Threads", "Status", "User", "Ports", "Command"]
COL_KEY = ["pid", "name", "cpu",  "mem_mb", "threads", "status", "user", "ports", "cmdline"]
COL_IDX = {name: i for i, name in enumerate(COLS)}

# Custom role so numeric columns sort numerically while the proxy still filters
# against DisplayRole text.
SORT_ROLE = Qt.UserRole + 1

_COL_TIPS = {
    "PID":     "Process ID — unique identifier assigned by the OS",
    "Name":    "Executable filename",
    "CPU %":   "CPU usage since last refresh (across all cores)",
    "Mem MB":  "Physical RAM in use — Resident Set Size (RSS)",
    "Threads": "Number of active threads",
    "Status":  "running · sleeping · stopped · zombie",
    "User":    "Account that owns the process",
    "Ports":   "Local ports with open network connections",
    "Command": "Full command line including all arguments",
}

_STATUS_COLOR: dict[str, QColor] = {
    "running":    QColor("#2d7a2d"),
    "sleeping":   QColor("#555"),
    "stopped":    QColor("#a05000"),
    "zombie":     QColor("#8b0000"),
    "disk-sleep": QColor("#555"),
}
_PORT_COLOR    = QColor("#5aafff")
_HIGH_CPU_COLOR = QColor("#f0a000")
_CMD_COLOR     = QColor("#888")
_DEFAULT_FG    = QColor("#ccc")

_ALIGN_RIGHT = Qt.AlignRight | Qt.AlignVCenter
_RIGHT_COLS = {COL_IDX["PID"], COL_IDX["CPU %"], COL_IDX["Mem MB"], COL_IDX["Threads"]}


class ProcessModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []

    # ── QAbstractTableModel interface ─────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        name = COLS[section]
        if role == Qt.DisplayRole:
            return name
        if role == Qt.ToolTipRole:
            return _COL_TIPS.get(name)
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._data[index.row()]
        col = index.column()
        key = COL_KEY[col]
        val = row[key]

        if role == Qt.DisplayRole:
            if key == "cpu":
                return f"{val:.1f}"
            if key == "mem_mb":
                return f"{val:.1f}"
            return str(val)

        if role == SORT_ROLE:
            return val if isinstance(val, (int, float)) else str(val).lower()

        if role == Qt.ForegroundRole:
            if key == "status":
                return _STATUS_COLOR.get(val, _DEFAULT_FG)
            if key == "ports" and val:
                return _PORT_COLOR
            if key == "cpu" and val > 20:
                return _HIGH_CPU_COLOR
            if key == "cmdline":
                return _CMD_COLOR

        if role == Qt.TextAlignmentRole and col in _RIGHT_COLS:
            return _ALIGN_RIGHT

        return None

    # ── diff update ───────────────────────────────────────────────────────────

    def update(self, incoming: list[dict]) -> None:
        """Diff against current data; emit granular signals. No full reset."""
        incoming_by_pid: dict[int, dict] = {r["pid"]: r for r in incoming}

        # 1. Remove rows whose PID vanished (iterate in reverse to keep indices stable)
        to_remove = [i for i, r in enumerate(self._data) if r["pid"] not in incoming_by_pid]
        for i in reversed(to_remove):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self._data[i]
            self.endRemoveRows()

        # 2. Update in-place rows that changed.
        # Collect contiguous dirty runs and emit one signal per run — avoids
        # marking unchanged rows between first/last dirty row as stale.
        current_pids: set[int] = set()
        dirty_runs: list[tuple[int, int]] = []
        run_start = -1
        nc = len(COLS) - 1
        for i, row in enumerate(self._data):
            current_pids.add(row["pid"])
            new = incoming_by_pid[row["pid"]]
            if row != new:
                self._data[i] = new
                if run_start < 0:
                    run_start = i
                run_end = i
            else:
                if run_start >= 0:
                    dirty_runs.append((run_start, run_end))
                    run_start = -1
        if run_start >= 0:
            dirty_runs.append((run_start, run_end))

        roles = [Qt.DisplayRole, Qt.ForegroundRole]
        for r0, r1 in dirty_runs:
            self.dataChanged.emit(self.index(r0, 0), self.index(r1, nc), roles)

        # 3. Append brand-new PIDs at the end
        new_rows = [r for r in incoming if r["pid"] not in current_pids]
        if new_rows:
            first = len(self._data)
            last = first + len(new_rows) - 1
            self.beginInsertRows(QModelIndex(), first, last)
            self._data.extend(new_rows)
            self.endInsertRows()

    def remove_pids(self, pids: set[int]) -> None:
        """Immediately remove rows by PID — call after kill for instant feedback."""
        to_remove = [i for i, r in enumerate(self._data) if r["pid"] in pids]
        for i in reversed(to_remove):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self._data[i]
            self.endRemoveRows()

    def process_at(self, row: int) -> dict | None:
        return self._data[row] if 0 <= row < len(self._data) else None


class AnyColumnFilter(QSortFilterProxyModel):
    """Filter that matches against all columns, not just one.

    Sorts via SORT_ROLE so numeric columns compare as numbers, not strings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)

    def filterAcceptsRow(self, src_row: int, src_parent: QModelIndex) -> bool:
        rx = self.filterRegularExpression()
        if not rx.pattern():
            return True
        model = self.sourceModel()
        for col in range(model.columnCount()):
            text = model.data(model.index(src_row, col, src_parent), Qt.DisplayRole)
            if text and rx.match(str(text)).hasMatch():
                return True
        return False
