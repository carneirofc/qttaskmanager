"""Main application window."""
import psutil

from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QPushButton, QMessageBox,
)

from .collector import CollectorWorker
from .proc_tab import ProcessTab
from .port_tab import ConnectionsTab
from .theme import DARK


class MainWindow(QMainWindow):
    # Signals cross the thread boundary safely (auto-connection = queued).
    # Never call worker methods directly from the main thread.
    _sig_pause = Signal()
    _sig_resume = Signal()
    _sig_force_refresh = Signal()
    _sig_shutdown = Signal()

    def __init__(self, interval_ms: int = 3000):
        super().__init__()
        self.setWindowTitle("Process Manager")
        self.resize(1300, 840)
        self.setStyleSheet(DARK)

        self._build_ui()
        self._start_worker(interval_ms)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._proc_tab = ProcessTab()
        self._proc_tab.kill_requested.connect(self._kill_processes)

        self._conn_tab = ConnectionsTab()
        self._pending_conns: list | None = None  # buffered while tab is hidden

        self._tabs = QTabWidget()
        self._tabs.addTab(self._proc_tab, "Processes")
        self._tabs.addTab(self._conn_tab, "All Connections")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.tabBar().setCursor(Qt.PointingHandCursor)
        self.setCentralWidget(self._tabs)

        self._status_label = QStatusBar()
        self._status_label.showMessage("Starting…")

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.setCheckable(True)
        self._btn_pause.setFixedWidth(72)
        self._btn_pause.setCursor(Qt.PointingHandCursor)
        self._btn_pause.setToolTip("Pause / resume automatic refresh (every 3 s)")
        self._btn_pause.clicked.connect(self._toggle_pause)

        self.setStatusBar(self._status_label)
        self._status_label.addPermanentWidget(self._btn_pause)

    # ── worker thread ─────────────────────────────────────────────────────────

    def _start_worker(self, interval_ms: int) -> None:
        self._thread = QThread(self)
        self._worker = CollectorWorker(interval_ms)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.start)
        self._worker.data_ready.connect(self._on_data)

        self._sig_pause.connect(self._worker.pause)
        self._sig_resume.connect(self._worker.resume)
        self._sig_force_refresh.connect(self._worker.force_refresh)
        self._sig_shutdown.connect(self._worker.shutdown)

        self._thread.start()

    # ── slots ─────────────────────────────────────────────────────────────────

    @Slot(list, list)
    def _on_data(self, procs: list, conns: list) -> None:
        self._proc_tab.on_data(procs, conns)

        # Only push to the connections model when that tab is visible.
        # beginResetModel/endResetModel on a hidden-but-connected view still
        # processes signals and repaints — waste on every tick.
        if self._tabs.currentWidget() is self._conn_tab:
            self._conn_tab.on_data(conns)
        else:
            self._pending_conns = conns  # flush on tab switch

        self._status_label.showMessage(
            f"{len(procs)} processes  ·  {len(conns)} connections"
        )

    def _on_tab_changed(self, _index: int) -> None:
        if self._tabs.currentWidget() is self._conn_tab and self._pending_conns is not None:
            self._conn_tab.on_data(self._pending_conns)
            self._pending_conns = None

    def _toggle_pause(self, checked: bool) -> None:
        if checked:
            self._sig_pause.emit()
            self._btn_pause.setText("Resume")
        else:
            self._sig_resume.emit()
            self._btn_pause.setText("Pause")

    @Slot(list)
    def _kill_processes(self, targets: list) -> None:
        if not targets:
            return

        if len(targets) == 1:
            pid, name = targets[0]
            body = f"Kill {name} (PID {pid})?"
        else:
            lines = "\n".join(f"  • {name}  (PID {pid})" for pid, name in targets)
            body = f"Kill {len(targets)} processes?\n\n{lines}"

        reply = QMessageBox.question(
            self, "Kill process" if len(targets) == 1 else "Kill processes",
            body, QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        killed_pids, killed_names = [], []
        denied, gone = [], []
        for pid, name in targets:
            try:
                psutil.Process(pid).kill()
                killed_pids.append(pid)
                killed_names.append(name)
            except psutil.NoSuchProcess:
                gone.append(name)
            except psutil.AccessDenied:
                denied.append(name)

        # Instant visual feedback — remove rows before background refresh arrives
        if killed_pids or [p for p, _ in targets if _ in gone]:
            vanished = set(killed_pids) | {p for p, n in targets if n in gone}
            self._proc_tab.remove_pids(vanished)

        parts = []
        if killed_names:
            parts.append(f"Killed {len(killed_names)}")
        if gone:
            parts.append(f"{len(gone)} already gone")
        if denied:
            parts.append(f"{len(denied)} access denied")
        self._status_label.showMessage("  ·  ".join(parts))

        if denied:
            QMessageBox.critical(
                self, "Access Denied",
                f"Could not kill: {', '.join(denied)}\n\nRun as administrator.",
            )
        if killed_pids or gone:
            self._sig_force_refresh.emit()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._sig_shutdown.emit()  # shuts down subprocess pool + timer
        self._thread.quit()
        self._thread.wait(3000)
        super().closeEvent(event)
