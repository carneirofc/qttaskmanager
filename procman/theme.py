"""Windows 11 dark theme — Fluent Design inspired."""

DARK = """
/* ── Base ──────────────────────────────────────────────────────────────── */
* {
    font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
    font-size: 14px;
}
QWidget {
    background-color: #202020;
    color: #ffffff;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}
QMainWindow {
    background: #1a1a1a;
}
QDialog {
    background: #202020;
}

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableView {
    background: #202020;
    alternate-background-color: #242424;
    border: none;
    outline: 0;
    gridline-color: transparent;
    show-decoration-selected: 1;
}
QTableView::item {
    padding: 3px 8px;
    border: none;
}
QTableView::item:selected {
    background: rgba(0, 120, 212, 0.30);
    color: #ffffff;
}
QTableView::item:selected:active {
    background: rgba(0, 120, 212, 0.45);
}
QTableView::item:hover:!selected {
    background: rgba(255, 255, 255, 0.04);
}

/* ── Header ─────────────────────────────────────────────────────────────── */
QHeaderView {
    background: transparent;
    border: none;
}
QHeaderView::section {
    background: #1a1a1a;
    color: rgba(255, 255, 255, 0.50);
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
    cursor: pointer;
}
QHeaderView::section:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #ffffff;
}
QHeaderView::section:last {
    border-right: none;
}
QHeaderView::up-arrow {
    width: 8px; height: 8px;
}
QHeaderView::down-arrow {
    width: 8px; height: 8px;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {
    background: rgba(255, 255, 255, 0.06);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 6px;
    padding: 6px 18px;
    cursor: pointer;
    min-width: 60px;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 0.10);
    border-color: rgba(255, 255, 255, 0.14);
}
QPushButton:pressed {
    background: rgba(255, 255, 255, 0.035);
    border-color: rgba(255, 255, 255, 0.06);
}
QPushButton:checked {
    background: #0067c0;
    border-color: rgba(255, 255, 255, 0.10);
}
QPushButton:checked:hover {
    background: #0078d4;
}
QPushButton:disabled {
    color: rgba(255, 255, 255, 0.28);
    background: rgba(255, 255, 255, 0.03);
    border-color: rgba(255, 255, 255, 0.04);
}

/* ── Input ───────────────────────────────────────────────────────────────── */
QLineEdit {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 6px;
    padding: 6px 12px;
    color: #ffffff;
}
QLineEdit:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.14);
}
QLineEdit:focus {
    background: rgba(255, 255, 255, 0.07);
    border-color: #0078d4;
    border-bottom-width: 2px;
}
QLineEdit::placeholder {
    color: rgba(255, 255, 255, 0.35);
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: transparent;
    top: -1px;
}
QTabBar {
    background: transparent;
}
QTabBar::tab {
    background: transparent;
    color: rgba(255, 255, 255, 0.50);
    padding: 10px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: 0;
    cursor: pointer;
}
QTabBar::tab:selected {
    color: #ffffff;
    border-bottom-color: #0078d4;
}
QTabBar::tab:hover:!selected {
    color: rgba(255, 255, 255, 0.80);
    background: rgba(255, 255, 255, 0.04);
}

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter::handle {
    background: rgba(255, 255, 255, 0.06);
}
QSplitter::handle:vertical {
    height: 3px;
    margin: 1px 0;
}
QSplitter::handle:horizontal {
    width: 3px;
    margin: 0 1px;
}
QSplitter::handle:hover {
    background: #0078d4;
}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.16);
    border-radius: 4px;
    min-height: 28px;
    margin: 1px 1px 1px 2px;
}
QScrollBar::handle:vertical:hover  { background: rgba(255, 255, 255, 0.32); }
QScrollBar::handle:vertical:pressed { background: #0078d4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.16);
    border-radius: 4px;
    min-width: 28px;
    margin: 2px 1px 1px 1px;
}
QScrollBar::handle:horizontal:hover  { background: rgba(255, 255, 255, 0.32); }
QScrollBar::handle:horizontal:pressed { background: #0078d4; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* ── Status bar ──────────────────────────────────────────────────────────── */
QStatusBar {
    background: #181818;
    color: rgba(255, 255, 255, 0.38);
    font-size: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding: 0 4px;
}
QStatusBar::item { border: none; }

/* ── Menu ────────────────────────────────────────────────────────────────── */
QMenu {
    background: #2c2c2c;
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    color: #ffffff;
    padding: 7px 20px 7px 12px;
    border-radius: 5px;
    margin: 1px 2px;
}
QMenu::item:selected {
    background: rgba(255, 255, 255, 0.08);
}
QMenu::item:disabled {
    color: rgba(255, 255, 255, 0.28);
}
QMenu::separator {
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
    margin: 4px 8px;
}

/* ── GroupBox ────────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -1px;
    color: rgba(255, 255, 255, 0.50);
    background: #202020;
    padding: 0 5px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}

/* ── TextEdit / code areas ───────────────────────────────────────────────── */
QTextEdit {
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 5px;
    color: #cccccc;
    selection-background-color: #0078d4;
}

/* ── Tooltip ─────────────────────────────────────────────────────────────── */
QToolTip {
    background: #2c2c2c;
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    opacity: 230;
}

/* ── MessageBox ──────────────────────────────────────────────────────────── */
QMessageBox { background: #2b2b2b; }
QMessageBox QLabel { color: #ffffff; background: transparent; }
"""
