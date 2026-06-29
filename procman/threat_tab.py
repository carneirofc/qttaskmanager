"""Threats tab — heuristic detection of processes that may be performing
attacks, data theft, persistence or coin-mining (read-only)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu

from .scan_tab import ScanTab
from .scan_model import ColumnSpec
from .threat_data import scan_threats


class ThreatScanTab(ScanTab):
    def columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec("PID", "pid", align="R", width=64, tooltip="Process id",
                       sort_key="pid"),
            ColumnSpec("Process", "name", width=170, tooltip="Process name"),
            ColumnSpec("Risk", "risk", colored=True, width=80,
                       tooltip="Severity band derived from the risk score",
                       sort_key="score_num"),
            ColumnSpec("Score", "score", align="R", width=60, colored=True,
                       tooltip="Weighted risk score (0–100)", sort_key="score_num"),
            ColumnSpec("Signature", "signature", width=90,
                       tooltip="signed · trusted-dir · unsigned · unknown"),
            ColumnSpec("Network", "network", width=120,
                       tooltip="External connections · ⚠ suspicious ports · listeners"),
            ColumnSpec("Findings", "findings",
                       tooltip="Heuristic rules this process tripped"),  # stretches
            ColumnSpec("Path", "exe", width=260, tooltip="Executable path"),
        ]

    def scan_callable(self):
        return scan_threats

    def banner_text(self) -> str:
        return ("🛈  Heuristic threat scan — read-only. Flags processes by behaviour "
                "(suspicious path, masquerading, encoded commands, C2 ports, "
                "persistence, mining). A high score is a prompt to investigate, "
                "not proof of malware — expect false positives.")

    def scan_label(self) -> str:
        return "Scan threats"

    def path_key(self) -> str | None:
        return "exe"

    def empty_hint(self) -> str:
        return "No suspicious process behaviour detected."

    def default_sort(self):
        return (3, Qt.DescendingOrder)  # Score, highest first

    def summary_text(self, rows: list[dict]) -> str:
        crit = sum(1 for r in rows if r.get("risk") == "Critical")
        high = sum(1 for r in rows if r.get("risk") == "High")
        parts = [f"{len(rows)} flagged"]
        if crit:
            parts.append(f"{crit} critical")
        if high:
            parts.append(f"{high} high")
        parts.append("investigate before acting")
        return " · ".join(parts)

    def add_extra_actions(self, menu: QMenu, row: dict) -> None:
        findings = row.get("findings", "")
        if findings:
            act = QAction("Copy findings", self)
            text = f"PID {row.get('pid')} {row.get('name')} " \
                   f"(score {row.get('score')}, {row.get('risk')})\n" \
                   + "\n".join(f"  • {f}" for f in findings.split("; "))
            act.triggered.connect(lambda: QApplication.clipboard().setText(text))
            menu.addAction(act)
