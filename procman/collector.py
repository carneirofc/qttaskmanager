"""Background worker: submits collection to a subprocess so psutil's GIL
usage never blocks the main thread.

Thread model:
  Main thread  ── UI, event loop, model updates
  Worker QThread ── blocks on future.result() while subprocess collects
  Subprocess ── psutil runs here; completely separate GIL
"""
from concurrent.futures import ProcessPoolExecutor, Future
from PySide6.QtCore import QObject, QTimer, Signal

from .data import collect_all


class CollectorWorker(QObject):
    """Owned by a background QThread. Emits data_ready on each collection."""

    data_ready = Signal(list, list)  # (processes, connections)

    def __init__(self, interval_ms: int = 3000, parent: QObject | None = None):
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._timer: QTimer | None = None
        self._paused = False
        self._executor: ProcessPoolExecutor | None = None

    # ── slots (all invoked via queued signal from main thread) ────────────────

    def start(self) -> None:
        """Called once via QThread.started — runs in the worker thread."""
        # max_workers=1: one subprocess, reused across collections.
        # First submit has ~0.5s spawn overhead; subsequent calls are instant.
        self._executor = ProcessPoolExecutor(max_workers=1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run)
        self._run()

    def pause(self) -> None:
        self._paused = True
        if self._timer:
            self._timer.stop()

    def resume(self) -> None:
        self._paused = False
        self._run()

    def force_refresh(self) -> None:
        if self._timer:
            self._timer.stop()
        self._run()

    def set_interval(self, ms: int) -> None:
        """Change the refresh cadence live (invoked via queued signal)."""
        self._interval_ms = max(200, int(ms))
        if self._timer and self._timer.isActive():
            self._timer.start(self._interval_ms)  # reschedule pending tick

    def shutdown(self) -> None:
        """Called before the thread is quit."""
        self._paused = True
        if self._timer:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    # ── internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        if self._executor is None:
            return
        try:
            # Blocks this worker thread — NOT the main thread.
            # The subprocess collects psutil data with its own GIL.
            procs, conns = self._executor.submit(collect_all).result()
            self.data_ready.emit(procs, conns)
        except Exception:
            pass  # subprocess crash or shutdown; skip cycle
        finally:
            if not self._paused and self._timer:
                self._timer.start(self._interval_ms)
