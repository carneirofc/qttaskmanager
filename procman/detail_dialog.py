"""Process detail dialog — shown on right-click → Inspect."""
import os
import subprocess
import psutil
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QTextEdit, QPushButton, QGroupBox, QSizePolicy,
)


def _label(text: str, selectable: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lbl


def _form_row(form: QFormLayout, title: str, value: str) -> None:
    form.addRow(f"<b>{title}</b>", _label(value or "—"))


class ProcessDetailDialog(QDialog):
    def __init__(self, proc: dict, conns: list[tuple], parent=None):
        super().__init__(parent)
        self._proc = proc
        self._conns = conns
        self.setWindowTitle(f"{proc['name']}  ·  PID {proc['pid']}")
        self.resize(760, 560)
        self.setMinimumSize(560, 380)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Compact top section (fixed height) ───────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        gen = QGroupBox("General")
        gen.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        gf = QFormLayout(gen)
        gf.setLabelAlignment(Qt.AlignRight)
        _form_row(gf, "PID",    str(self._proc["pid"]))
        _form_row(gf, "Name",   self._proc["name"])
        _form_row(gf, "Status", self._proc["status"])
        _form_row(gf, "User",   self._proc["user"])
        try:
            p = psutil.Process(self._proc["pid"])
            with p.oneshot():
                try:
                    ct = datetime.fromtimestamp(p.create_time()).strftime("%Y-%m-%d  %H:%M:%S")
                    _form_row(gf, "Started", ct)
                except Exception:
                    pass
                try:
                    _form_row(gf, "Open files", str(len(p.open_files())))
                except Exception:
                    pass
                try:
                    _form_row(gf, "Children", str(len(p.children())))
                except Exception:
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        top.addWidget(gen)

        res = QGroupBox("Resources")
        res.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        rf = QFormLayout(res)
        rf.setLabelAlignment(Qt.AlignRight)
        _form_row(rf, "CPU %",   f"{self._proc['cpu']:.1f} %")
        _form_row(rf, "Memory",  f"{self._proc['mem_mb']:.1f} MB")
        _form_row(rf, "Threads", str(self._proc["threads"]))
        top.addWidget(res)

        root.addLayout(top)

        # ── Executable path (fixed height) ───────────────────────────────────
        exe_box = QGroupBox("Executable")
        exe_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ef = QVBoxLayout(exe_box)
        exe_lbl = _label(self._proc.get("exe") or "—")
        exe_lbl.setFont(QFont("Consolas", 10))
        ef.addWidget(exe_lbl)
        root.addWidget(exe_box)

        # ── Command line — expands to fill remaining vertical space ───────────
        cmd_box = QGroupBox("Command line")
        cmd_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cl = QVBoxLayout(cmd_box)
        cl.setContentsMargins(4, 4, 4, 4)
        cmd_edit = QTextEdit()
        cmd_edit.setReadOnly(True)
        cmd_edit.setPlainText(self._proc.get("cmdline") or "—")
        cmd_edit.setFont(QFont("Consolas", 10))
        cmd_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cmd_edit.setStyleSheet("background:#141414; border:none; color:#aaa;")
        cl.addWidget(cmd_edit)
        root.addWidget(cmd_box, stretch=1)  # ← takes all remaining vertical space

        # ── Connections (fixed height, shown only when present) ───────────────
        pid = self._proc["pid"]
        my_conns = [c for c in self._conns if c[0] == pid]
        if my_conns:
            conn_box = QGroupBox(f"Connections  ({len(my_conns)})")
            conn_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cl2 = QVBoxLayout(conn_box)
            cl2.setContentsMargins(4, 4, 4, 4)
            lines = "\n".join(
                f"{c[2]:30s}  →  {c[3]:30s}  {c[4]}" for c in my_conns
            )
            te = QTextEdit()
            te.setReadOnly(True)
            te.setPlainText(lines)
            te.setFont(QFont("Consolas", 10))
            te.setMinimumHeight(80)
            te.setMaximumHeight(160)
            te.setStyleSheet("background:#141414; border:none; color:#5aafff;")
            cl2.addWidget(te)
            root.addWidget(conn_box)

        # ── Buttons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if self._proc.get("exe"):
            btn_loc = QPushButton("Open file location")
            btn_loc.setCursor(Qt.PointingHandCursor)
            btn_loc.setToolTip(f"Open Explorer and select:\n{self._proc.get('exe')}")
            btn_loc.clicked.connect(self._open_location)
            btn_row.addWidget(btn_loc)
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _open_location(self) -> None:
        exe = self._proc.get("exe", "")
        if exe and os.path.exists(exe):
            subprocess.Popen(["explorer", "/select,", exe])
        elif exe:
            folder = os.path.dirname(exe)
            if os.path.isdir(folder):
                os.startfile(folder)


def open_file_location(exe: str) -> None:
    """Open Explorer at the given executable path, selecting it."""
    if not exe:
        return
    if os.path.exists(exe):
        subprocess.Popen(["explorer", "/select,", exe])
    else:
        folder = os.path.dirname(exe)
        if os.path.isdir(folder):
            os.startfile(folder)
