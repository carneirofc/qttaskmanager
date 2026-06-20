"""App Data tab — browse per-application data folders across the AppData roots."""
from __future__ import annotations

from PySide6.QtCore import Qt

from .scan_tab import ScanTab
from .scan_model import ColumnSpec
from .scan_data import human_size
from .appdata_data import scan_appdata


class AppDataTab(ScanTab):
    def columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec("Application / Vendor", "app", width=260,
                       tooltip="Top-level folder under an AppData root"),
            ColumnSpec("Location", "root", width=120,
                       tooltip="Roaming · Local · LocalLow · ProgramData"),
            ColumnSpec("Size", "size_h", align="R", width=90, tooltip="Total size on disk",
                       sort_key="size_bytes"),
            ColumnSpec("Items", "items", align="R", width=80, tooltip="Number of files",
                       sort_key="items"),
            ColumnSpec("Path", "path", tooltip="Full path — Open in Explorer to inspect"),
        ]

    def scan_callable(self):
        return scan_appdata

    def banner_text(self) -> str:
        return ("🛈  Read-only — lists application data folders under Roaming, Local, "
                "LocalLow and ProgramData. Right-click → Open in Explorer to inspect; "
                "nothing is deleted.")

    def scan_label(self) -> str:
        return "Scan app data"

    def path_key(self) -> str | None:
        return "path"

    def empty_hint(self) -> str:
        return "No application data folders found."

    def default_sort(self):
        return (2, Qt.DescendingOrder)  # Size, largest first

    def summary_text(self, rows: list[dict]) -> str:
        total = sum(r.get("size_bytes", 0) for r in rows)
        return f"{len(rows)} app folders · {human_size(total)} total"
