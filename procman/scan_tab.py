"""Base class for the on-demand scan tabs (disk / registry / links).

Provides the shared chrome — read-only safety banner, Scan/Cancel button, a
disabled placeholder for the (intentionally unimplemented) cleanup action, a
filter box, summary label, indeterminate progress bar, results table and a
non-destructive context menu (Open in Explorer / Copy path).

Subclasses declare columns(), scan_callable(), banner_text() and a few labels.
NOTHING here deletes or modifies anything — the scanners are strictly read-only.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from threading import Event

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QProgressBar, QMenu, QApplication,
)

from .scan_model import ScanTableModel, ScanFilter, ColumnSpec
from .scan_worker import ScanRunnable
from .widgets import make_table
from .detail_dialog import open_file_location


class ScanTab(QWidget):
    # ── hooks for subclasses ──────────────────────────────────────────────────

    def columns(self) -> list[ColumnSpec]:
        raise NotImplementedError

    def scan_callable(self) -> Callable[[Event, Callable[[str], None]], list]:
        raise NotImplementedError

    def banner_text(self) -> str:
        return "Read-only scan. Nothing is modified — review flagged items manually."

    def scan_label(self) -> str:
        return "Scan"

    def action_label(self) -> str | None:
        """Label for the disabled cleanup placeholder, or None for no button."""
        return None

    def path_key(self) -> str | None:
        """Row key holding a filesystem path, for Open in Explorer / Copy path."""
        return None

    def empty_hint(self) -> str:
        return "No issues found."

    def summary_text(self, rows: list[dict]) -> str:
        return f"{len(rows)} items"

    def default_sort(self) -> tuple[int, Qt.SortOrder] | None:
        return None

    def add_extra_actions(self, menu: QMenu, row: dict) -> None:
        """Subclasses may add further non-destructive context actions."""

    # ── construction ──────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ScanTableModel(self.columns())
        self._proxy = ScanFilter()
        self._proxy.setSourceModel(self._model)

        self._cancel = Event()
        self._running = False
        self._runnable: ScanRunnable | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)

        banner = QLabel(self.banner_text())
        banner.setObjectName("scanBanner")
        banner.setWordWrap(True)
        layout.addWidget(banner)

        layout.addLayout(self._build_toolbar())

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)         # indeterminate
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._table = make_table(self._proxy)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.horizontalHeader().setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._table)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()

        self._btn = QPushButton(self.scan_label())
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self._on_button)
        bar.addWidget(self._btn)

        action = self.action_label()
        if action:
            # Intentionally disabled — cleanup/removal is NOT implemented.
            # TODO: implement the actual cleanup action here (currently a
            # read-only scanner by design — see banner).
            placeholder = QPushButton(action)
            placeholder.setEnabled(False)
            placeholder.setToolTip(
                "Not implemented — this is a read-only scanner.\n"
                "Review the flagged items and clean them up manually."
            )
            bar.addWidget(placeholder)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter results…")
        self._search.setToolTip("Filter across all columns (case-insensitive)")
        self._search.textChanged.connect(self._proxy.setFilterFixedString)
        bar.addWidget(self._search, 1)

        self._summary = QLabel("Not scanned yet")
        self._summary.setStyleSheet("color: #777;")
        bar.addWidget(self._summary)
        return bar

    # ── scan lifecycle ────────────────────────────────────────────────────────

    def run_scan(self) -> None:
        """Public entry point — also used by the Tools › Run all scans menu."""
        if self._running:
            return
        self._running = True
        self._cancel.clear()
        self._btn.setText("Cancel")
        self._progress.setVisible(True)
        self._summary.setText("Scanning…")

        r = ScanRunnable(self.scan_callable(), self._cancel)
        r.signals.progress.connect(self._on_progress)
        r.signals.finished.connect(self._on_finished)
        r.signals.failed.connect(self._on_failed)
        self._runnable = r
        QThreadPool.globalInstance().start(r)

    def shutdown(self) -> None:
        """Stop any in-flight scan and stop delivering its results.

        Called on window close: disconnecting the runnable's signals first means
        a worker that is still finishing can't emit into an about-to-be-destroyed
        widget (the cancel Event makes it bail almost immediately anyway).
        """
        self._cancel.set()
        if self._runnable is not None:
            try:
                self._runnable.signals.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._runnable = None

    def _on_button(self) -> None:
        if self._running:
            self._cancel.set()
            self._summary.setText("Cancelling…")
        else:
            self.run_scan()

    def _on_progress(self, msg: str) -> None:
        self._summary.setText(msg)

    def _on_finished(self, rows: list[dict]) -> None:
        self._model.load(rows)
        srt = self.default_sort()
        if srt is not None:
            self._proxy.sort(srt[0], srt[1])
            self._table.horizontalHeader().setSortIndicator(srt[0], srt[1])
        self._finish()
        self._summary.setText(self.summary_text(rows) if rows else self.empty_hint())

    def _on_failed(self, err: str) -> None:
        self._finish()
        self._summary.setText(f"Scan failed — {err}")

    def _finish(self) -> None:
        self._running = False
        self._btn.setText(self.scan_label())
        self._progress.setVisible(False)
        self._runnable = None

    # ── context menu (non-destructive only) ───────────────────────────────────

    def _context_menu(self, pos) -> None:
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        self._table.setCurrentIndex(idx)  # highlight the row being acted on
        row = self._model.row_at(self._proxy.mapToSource(idx).row())
        if not row:
            return

        menu = QMenu(self)
        pk = self.path_key()
        path = row.get(pk, "") if pk else ""
        if path:
            target = path if os.path.exists(path) else os.path.dirname(path)
            act_open = QAction("Open in Explorer", self)
            act_open.setEnabled(bool(target) and os.path.exists(target))
            act_open.triggered.connect(lambda: self._open_path(path))
            menu.addAction(act_open)

            act_copy = QAction("Copy path", self)
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(path))
            menu.addAction(act_copy)

        self.add_extra_actions(menu, row)

        if not menu.isEmpty():
            menu.exec(self._table.viewport().mapToGlobal(pos))

    def _open_path(self, path: str) -> None:
        if os.path.isdir(path):
            os.startfile(path)  # noqa: S606 — opening Explorer at a folder
        else:
            open_file_location(path)
