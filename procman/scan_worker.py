"""On-demand scan execution on the global QThreadPool.

Each scan callable has the signature  fn(cancel: Event, progress: Callable[[str], None]) -> list[dict]
and is expected to poll `cancel` in its loops and call `progress` with a short
status string. Results cross back to the GUI thread via queued signals.
"""
from __future__ import annotations

from collections.abc import Callable
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal


class WorkerSignals(QObject):
    started  = Signal()
    progress = Signal(str)
    finished = Signal(list)   # list[dict] (may be partial if cancelled)
    failed   = Signal(str)


class ScanRunnable(QRunnable):
    def __init__(self, fn: Callable[[Event, Callable[[str], None]], list], cancel: Event):
        super().__init__()
        self._fn = fn
        self._cancel = cancel
        self.signals = WorkerSignals()
        # We keep our own reference in the tab and clear it on completion, so the
        # Python-side WorkerSignals object can't be collected mid-run.
        self.setAutoDelete(False)

    def run(self) -> None:
        self.signals.started.emit()
        try:
            rows = self._fn(self._cancel, self.signals.progress.emit)
            self.signals.finished.emit(rows or [])
        except Exception as exc:  # surface the message instead of crashing the pool
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
