"""Connection/port table model."""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QColor

from .proc_model import AnyColumnFilter

COLS = ["PID", "Name", "Local Addr", "Remote Addr", "State", "Family"]
_STATE_COL = COLS.index("State")

_STATE_COLOR: dict[str, QColor] = {
    "established": QColor("#2d7a2d"),
    "listen":      QColor("#5aafff"),
    "time_wait":   QColor("#a05000"),
    "close_wait":  QColor("#888"),
    "syn_sent":    QColor("#a0a000"),
}
_DEFAULT_FG = QColor("#5aafff")


class PortModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[tuple] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        col = index.column()
        val = self._rows[index.row()][col]

        if role == Qt.DisplayRole:
            return str(val)

        if role == Qt.ForegroundRole and col == _STATE_COL:
            return _STATE_COLOR.get(str(val).lower(), _DEFAULT_FG)

        return None

    def load(self, rows: list[tuple]) -> None:
        old_len = len(self._rows)
        new_len = len(rows)

        # Overwrite overlapping range in-place
        keep = min(old_len, new_len)
        changed_top = -1
        changed_bot = -1
        for i in range(keep):
            if self._rows[i] != rows[i]:
                self._rows[i] = rows[i]
                if changed_top < 0:
                    changed_top = i
                changed_bot = i

        if changed_top >= 0:
            self.dataChanged.emit(
                self.index(changed_top, 0),
                self.index(changed_bot, len(COLS) - 1),
                [Qt.DisplayRole, Qt.ForegroundRole],
            )

        if old_len > new_len:
            self.beginRemoveRows(QModelIndex(), new_len, old_len - 1)
            del self._rows[new_len:]
            self.endRemoveRows()
        elif new_len > old_len:
            self.beginInsertRows(QModelIndex(), old_len, new_len - 1)
            self._rows.extend(rows[old_len:])
            self.endInsertRows()

    def filter_pid(self, pid: int) -> list[tuple]:
        return [r for r in self._rows if r[0] == pid]


def make_filtered_port_model(source: PortModel) -> AnyColumnFilter:
    proxy = AnyColumnFilter()
    proxy.setSourceModel(source)
    proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
    return proxy
