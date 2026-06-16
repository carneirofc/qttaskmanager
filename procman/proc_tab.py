"""Process tab: table + per-process connection detail + controls."""
import psutil

from PySide6.QtCore import Qt, Signal, QModelIndex
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QMenu, QMessageBox,
)

from .proc_model import ProcessModel, AnyColumnFilter, COL_IDX
from .port_model import PortModel, make_filtered_port_model
from .detail_dialog import ProcessDetailDialog, open_file_location
from .widgets import make_table


class ProcessTab(QWidget):
    kill_requested = Signal(list)  # list[(pid, name)] — window handles confirmation

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc_model = ProcessModel()
        self._proxy = AnyColumnFilter()
        self._proxy.setSourceModel(self._proc_model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._detail_model = PortModel()
        self._detail_proxy = make_filtered_port_model(self._detail_model)

        self._all_conns: list[tuple] = []

        self._build_ui()

    # ── public API ────────────────────────────────────────────────────────────

    def remove_pids(self, pids: set[int]) -> None:
        self._proc_table.setUpdatesEnabled(False)
        try:
            self._proc_model.remove_pids(pids)
        finally:
            self._proc_table.setUpdatesEnabled(True)

    def on_data(self, procs: list[dict], conns: list[tuple]) -> None:
        """Called from main window when collector emits new data.

        Model signals (dataChanged, beginInsertRows, etc.) are batched behind
        setUpdatesEnabled so the view repaints exactly once per cycle.
        No sort() call here — that emits layoutAboutToBeChanged/layoutChanged
        which stalls the main thread every refresh. Sort order is stable;
        user clicks a column header to change it.
        """
        self._proc_table.setUpdatesEnabled(False)
        try:
            self._proc_model.update(procs)
        finally:
            self._proc_table.setUpdatesEnabled(True)

        self._all_conns = conns
        self._refresh_detail()
        self._lbl_count.setText(f"{len(procs)} processes")

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)

        layout.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_proc_table())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([580, 200])
        layout.addWidget(splitter)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter processes…")
        self._search.setToolTip("Filter by name, PID, user, command, port…  (case-insensitive)")
        self._search.textChanged.connect(self._on_filter_changed)
        self._lbl_count = QLabel("0 processes")
        self._lbl_count.setStyleSheet("color: #555;")
        self._lbl_count.setToolTip("Total processes visible in current filter")
        bar.addWidget(self._search)
        bar.addWidget(self._lbl_count)
        return bar

    def _build_proc_table(self) -> QWidget:
        self._proc_table = make_table(self._proxy)
        self._proc_table.setSelectionMode(
            self._proc_table.SelectionMode.ExtendedSelection
        )
        self._proxy.setDynamicSortFilter(False)
        self._proxy.sort(COL_IDX["CPU %"], Qt.DescendingOrder)
        hdr = self._proc_table.horizontalHeader()
        hdr.setSortIndicator(COL_IDX["CPU %"], Qt.DescendingOrder)
        hdr.setCursor(Qt.PointingHandCursor)
        hdr.setToolTip("Click a column to sort")
        self._proc_table.selectionModel().selectionChanged.connect(self._refresh_detail)
        self._proc_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._proc_table.customContextMenuRequested.connect(self._context_menu)

        hdr.resizeSection(COL_IDX["PID"],     60)
        hdr.resizeSection(COL_IDX["Name"],    180)
        hdr.resizeSection(COL_IDX["CPU %"],   65)
        hdr.resizeSection(COL_IDX["Mem MB"],  75)
        hdr.resizeSection(COL_IDX["Threads"], 65)
        hdr.resizeSection(COL_IDX["Status"],  85)
        hdr.resizeSection(COL_IDX["User"],    120)
        hdr.resizeSection(COL_IDX["Ports"],   120)
        # "Command" is the stretch column (last)

        return self._proc_table

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        self._detail_label = QLabel("Select a process to see its connections")
        self._detail_label.setStyleSheet("color: #555; padding: 0 4px;")
        layout.addWidget(self._detail_label)
        detail_table = make_table(self._detail_proxy)
        layout.addWidget(detail_table)
        return panel

    # ── internal ──────────────────────────────────────────────────────────────

    def _on_filter_changed(self, text: str) -> None:
        # setFilterFixedString internally calls invalidate() which re-filters
        # AND re-sorts in one pass. No extra sort() call needed.
        self._proxy.setFilterFixedString(text)

    def _selected_proc(self) -> dict | None:
        """Current (last-clicked) process — used for single-item actions."""
        idx = self._proc_table.selectionModel().currentIndex()
        if not idx.isValid():
            return None
        src = self._proxy.mapToSource(idx)
        return self._proc_model.process_at(src.row())

    def _selected_procs(self) -> list[dict]:
        """All highlighted rows, deduplicated by PID."""
        seen: set[int] = set()
        result: list[dict] = []
        for idx in self._proc_table.selectionModel().selectedRows():
            src = self._proxy.mapToSource(idx)
            proc = self._proc_model.process_at(src.row())
            if proc and proc["pid"] not in seen:
                seen.add(proc["pid"])
                result.append(proc)
        return result

    def _refresh_detail(self) -> None:
        proc = self._selected_proc()
        if not proc:
            return
        rows = [r for r in self._all_conns if r[0] == proc["pid"]]
        self._detail_model.load(rows)
        self._detail_label.setText(
            f"Connections — PID {proc['pid']}  ·  {proc['name']}"
        )

    def _context_menu(self, pos) -> None:
        if not self._proc_table.indexAt(pos).isValid():
            return
        procs = self._selected_procs()
        if not procs:
            return

        single = len(procs) == 1
        proc = procs[0]  # primary (last-clicked) for single-item actions
        menu = QMenu(self)

        # ── single-process actions ────────────────────────────────────────────
        act_inspect = QAction("Inspect…", self)
        act_inspect.setEnabled(single)
        act_inspect.triggered.connect(lambda: self._inspect(proc))
        menu.addAction(act_inspect)

        act_loc = QAction("Open file location", self)
        act_loc.setEnabled(single and bool(proc.get("exe")))
        act_loc.triggered.connect(lambda: open_file_location(proc.get("exe", "")))
        menu.addAction(act_loc)

        menu.addSeparator()

        # ── kill (works for 1 or many) ────────────────────────────────────────
        if single:
            label = f"Kill  PID {proc['pid']}  ({proc['name']})"
        else:
            label = f"Kill {len(procs)} processes"
        act_kill = QAction(label, self)
        act_kill.triggered.connect(
            lambda: self.kill_requested.emit([(p["pid"], p["name"]) for p in procs])
        )
        menu.addAction(act_kill)

        menu.exec(self._proc_table.viewport().mapToGlobal(pos))

    def _inspect(self, proc: dict) -> None:
        dlg = ProcessDetailDialog(proc, self._all_conns, parent=self)
        dlg.exec()
