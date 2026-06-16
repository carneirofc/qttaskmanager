"""All-connections tab."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel

from .port_model import PortModel, make_filtered_port_model
from .widgets import make_table


class ConnectionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = PortModel()
        self._proxy = make_filtered_port_model(self._model)
        self._build_ui()

    # ── public API ────────────────────────────────────────────────────────────

    def on_data(self, conns: list[tuple]) -> None:
        self._model.load(conns)
        self._lbl_count.setText(f"{len(conns)} connections")

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Filter by address, port, state, name…")
        search.textChanged.connect(self._proxy.setFilterFixedString)
        self._lbl_count = QLabel("0 connections")
        self._lbl_count.setStyleSheet("color: #555;")
        bar.addWidget(search)
        bar.addWidget(self._lbl_count)
        layout.addLayout(bar)

        table = make_table(self._proxy)
        layout.addWidget(table)
