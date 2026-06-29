"""Main application window."""
import psutil

from PySide6.QtCore import QThread, Signal, Slot, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QPushButton, QMessageBox, QApplication,
    QDialog,
)

from .collector import CollectorWorker
from .proc_tab import ProcessTab
from .port_tab import ConnectionsTab
from .disk_tab import DiskCleanupTab
from .registry_tab import RegistryTab
from .links_tab import BrokenLinksTab
from .appdata_tab import AppDataTab
from .threat_tab import ThreatScanTab
from .theme import stylesheet, THEMES
from .settings import AppSettings
from .settings_dialog import SettingsDialog
from . import version


class MainWindow(QMainWindow):
    # Signals cross the thread boundary safely (auto-connection = queued).
    # Never call worker methods directly from the main thread.
    _sig_pause = Signal()
    _sig_resume = Signal()
    _sig_force_refresh = Signal()
    _sig_set_interval = Signal(int)
    _sig_shutdown = Signal()

    def __init__(self, interval_ms: int = 1000):
        super().__init__()
        self.setWindowTitle("Qt Task Manager")
        self.resize(1300, 840)

        # Persisted preferences (theme, refresh interval, geometry).
        self._settings = AppSettings()
        self._theme_name = self._settings.theme()
        self._interval_ms = self._settings.interval_ms(default=interval_ms)
        self._theme_actions: dict[str, QAction] = {}
        QApplication.instance().setStyleSheet(stylesheet(self._theme_name))

        self._build_ui()
        self._build_menubar()
        self._start_worker(self._interval_ms)

        geo = self._settings.geometry()
        if geo:
            self.restoreGeometry(geo)

        # Kick off every read-only scan once the event loop is running so the
        # window paints first and the scans run in the background thread pool.
        QTimer.singleShot(0, self._run_all_scans)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._proc_tab = ProcessTab()
        self._proc_tab.kill_requested.connect(self._kill_processes)

        self._conn_tab = ConnectionsTab()
        self._pending_conns: list | None = None  # buffered while tab is hidden

        # On-demand, read-only system scanners (no live feed — button driven).
        self._threat_tab = ThreatScanTab()
        self._disk_tab = DiskCleanupTab()
        self._appdata_tab = AppDataTab()
        self._registry_tab = RegistryTab()
        self._links_tab = BrokenLinksTab()
        self._scan_tabs = (
            self._threat_tab, self._disk_tab, self._appdata_tab,
            self._registry_tab, self._links_tab,
        )

        self._tabs = QTabWidget()
        self._tabs.addTab(self._proc_tab, "Processes")
        self._tabs.addTab(self._conn_tab, "All Connections")
        self._tabs.addTab(self._threat_tab, "Threats")
        self._tabs.addTab(self._disk_tab, "Disk Cleanup")
        self._tabs.addTab(self._appdata_tab, "App Data")
        self._tabs.addTab(self._registry_tab, "Registry")
        self._tabs.addTab(self._links_tab, "Broken Links")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.tabBar().setCursor(Qt.PointingHandCursor)
        self.setCentralWidget(self._tabs)

        self._status_label = QStatusBar()
        self._status_label.showMessage("Starting…")

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.setCheckable(True)
        self._btn_pause.setFixedWidth(72)
        self._btn_pause.setCursor(Qt.PointingHandCursor)
        self._btn_pause.clicked.connect(self._toggle_pause)
        self._update_pause_tooltip()

        self.setStatusBar(self._status_label)
        self._status_label.addPermanentWidget(self._btn_pause)

    def _update_pause_tooltip(self) -> None:
        secs = self._interval_ms / 1000
        self._btn_pause.setToolTip(f"Pause / resume automatic refresh (every {secs:g} s)")

    def _build_menubar(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        act_settings = QAction("&Settings…", self)
        act_settings.triggered.connect(self._open_settings)
        file_menu.addAction(act_settings)
        file_menu.addSeparator()
        act_exit = QAction("E&xit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        tools = mb.addMenu("&Tools")
        for label, tab in (
            ("Scan &Threats",      self._threat_tab),
            ("Scan &Disk Cleanup", self._disk_tab),
            ("Scan &App Data",     self._appdata_tab),
            ("Scan &Registry",     self._registry_tab),
            ("Scan Broken &Links", self._links_tab),
        ):
            act = QAction(label, self)
            act.triggered.connect(lambda _=False, t=tab: self._show_and_scan(t))
            tools.addAction(act)
        tools.addSeparator()
        act_all = QAction("Run &All Scans", self)
        act_all.triggered.connect(self._run_all_scans)
        tools.addAction(act_all)

        view = mb.addMenu("&View")
        theme_menu = view.addMenu("&Theme")
        group = QActionGroup(self)
        group.setExclusive(True)
        for name in THEMES:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == self._theme_name)
            act.triggered.connect(lambda _=False, n=name: self._apply_theme(n))
            group.addAction(act)
            theme_menu.addAction(act)
            self._theme_actions[name] = act

        help_menu = mb.addMenu("&Help")
        act_about = QAction("&About", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

    def _show_and_scan(self, tab) -> None:
        self._tabs.setCurrentWidget(tab)
        tab.run_scan()

    def _run_all_scans(self) -> None:
        for tab in self._scan_tabs:
            tab.run_scan()  # all run concurrently on the global thread pool

    def _apply_theme(self, name: str) -> None:
        self._theme_name = name
        QApplication.instance().setStyleSheet(stylesheet(name))
        self._settings.set_theme(name)
        self._settings.sync()
        act = self._theme_actions.get(name)   # keep View > Theme in sync
        if act and not act.isChecked():
            act.setChecked(True)

    def _set_interval(self, ms: int) -> None:
        self._interval_ms = ms
        self._sig_set_interval.emit(ms)        # queued → collector thread
        self._update_pause_tooltip()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() != QDialog.Accepted:
            return
        theme = dlg.selected_theme()
        interval = dlg.selected_interval_ms()
        if theme != self._theme_name:
            self._apply_theme(theme)
        if interval != self._interval_ms:
            self._settings.set_interval_ms(interval)
            self._set_interval(interval)
        self._settings.sync()

    def _about(self) -> None:
        QMessageBox.about(
            self, "About Qt Task Manager",
            "<b>Qt Task Manager</b><br>"
            f"Version {version.version()} "
            f"(commit {version.commit()}, built {version.build_date()})"
            "<br><br>"
            "Live processes &amp; network connections, plus read-only system "
            "scanners for disk cleanup, registry hygiene and broken shortcuts."
            "<br><br>The scanners never modify or delete anything — they only "
            "report what you may want to review."
            "<br><br>Author: carneirofc<br>"
            'Repository: <a href="https://github.com/carneirofc/qttaskmanager">'
            "github.com/carneirofc/qttaskmanager</a>",
        )

    # ── worker thread ─────────────────────────────────────────────────────────

    def _start_worker(self, interval_ms: int) -> None:
        self._thread = QThread(self)
        self._worker = CollectorWorker(interval_ms)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.start)
        self._thread.finished.connect(self._worker.deleteLater)
        self._worker.data_ready.connect(self._on_data)

        self._sig_pause.connect(self._worker.pause)
        self._sig_resume.connect(self._worker.resume)
        self._sig_force_refresh.connect(self._worker.force_refresh)
        self._sig_set_interval.connect(self._worker.set_interval)
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
        self._settings.set_geometry(self.saveGeometry())   # remember window size/pos
        self._settings.sync()

        for tab in self._scan_tabs:       # signal any in-flight scan to stop
            tab.shutdown()
        QThreadPool.globalInstance().waitForDone(2000)

        self._sig_shutdown.emit()  # shuts down subprocess pool + timer
        self._thread.quit()
        self._thread.wait(3000)
        super().closeEvent(event)
