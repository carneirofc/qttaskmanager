"""Disk Cleanup tab — sizes of well-known junk/cache locations (read-only)."""
from __future__ import annotations

from PySide6.QtCore import Qt

from .scan_tab import ScanTab
from .scan_model import ColumnSpec
from .scan_data import human_size
from .disk_data import scan_disk_cleanup


class DiskCleanupTab(ScanTab):
    def columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec("Location", "name",   tooltip="Well-known cache / temp location"),
            ColumnSpec("Path",     "path",   tooltip="Filesystem path"),
            ColumnSpec("Size",     "size_h", align="R", tooltip="Total size on disk",
                       sort_key="size_bytes"),
            ColumnSpec("Files",    "file_count", align="R", tooltip="Number of files",
                       sort_key="file_count"),
            ColumnSpec("Recommendation", "rec", colored=True,
                       tooltip="Suggested handling — review before deleting anything"),
            ColumnSpec("Note",     "note",   tooltip="What this location holds"),
        ]

    def scan_callable(self):
        return scan_disk_cleanup

    def banner_text(self) -> str:
        return ("🛈  Read-only scan — no files are deleted. Sizes are reported so you "
                "can decide what to clear manually. Cleanup is not implemented (TODO).")

    def scan_label(self) -> str:
        return "Scan disk"

    def action_label(self) -> str | None:
        return "Clean selected…"

    def path_key(self) -> str | None:
        return "path"

    def empty_hint(self) -> str:
        return "No known cleanup locations found on this system."

    def default_sort(self):
        return (2, Qt.DescendingOrder)  # Size, largest first

    def summary_text(self, rows: list[dict]) -> str:
        total = sum(r.get("size_bytes", 0) for r in rows)
        return f"{len(rows)} locations · {human_size(total)} total · review before deleting"
