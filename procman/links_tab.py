"""Broken Links tab — shortcuts whose target no longer exists (read-only)."""
from __future__ import annotations

from .scan_tab import ScanTab
from .scan_model import ColumnSpec
from .links_data import scan_broken_links


class BrokenLinksTab(ScanTab):
    def columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec("Shortcut", "name",   tooltip="Shortcut display name"),
            ColumnSpec("Location", "source", tooltip="Where the shortcut lives"),
            ColumnSpec("Target",   "target", tooltip="Missing executable the shortcut points to"),
            ColumnSpec("Status",   "status", colored=True, tooltip="Why this shortcut is flagged"),
        ]

    def scan_callable(self):
        return scan_broken_links

    def banner_text(self) -> str:
        return ("🛈  Read-only scan — no shortcuts are deleted. Lists Start Menu / "
                "Desktop shortcuts whose target application is gone. Removal is not "
                "implemented (TODO).")

    def scan_label(self) -> str:
        return "Scan shortcuts"

    def action_label(self) -> str | None:
        return "Delete shortcuts…"

    def path_key(self) -> str | None:
        return "link"  # select the .lnk itself in Explorer

    def empty_hint(self) -> str:
        return "No broken shortcuts found."

    def summary_text(self, rows: list[dict]) -> str:
        return f"{len(rows)} broken shortcut(s) found"
