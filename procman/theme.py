"""Theming — a single Fluent-inspired QSS template rendered against a palette.

The stylesheet is authored once as a string.Template (so CSS braces pass
through untouched and only ``${name}`` slots are substituted). Each palette
fills those slots, giving several selectable themes that can be swapped live
via ``QApplication.setStyleSheet(stylesheet(name))``.
"""
from __future__ import annotations

from string import Template

# ── palette construction ──────────────────────────────────────────────────────

def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgba(h: str, a: str) -> str:
    r, g, b = _rgb(h)
    return f"rgba({r}, {g}, {b}, {a})"


def _theme(
    name: str, *,
    bg: str, bg_deep: str, surface: str, row_alt: str, header_bg: str, code_bg: str,
    text: str, text_dim: str, text_faint: str,
    accent: str, accent_hi: str, accent_lo: str,
    overlay: str = "255, 255, 255", on_accent: str = "#ffffff",
    border_a: str = "0.09", border_strong_a: str = "0.14",
    hover_a: str = "0.06", hover_strong_a: str = "0.10",
    field_a: str = "0.05", scroll_a: str = "0.16", scroll_hi_a: str = "0.32",
) -> dict[str, str]:
    """Build a substitution dict. Translucent slots are derived from one overlay
    colour (white by default, accent-tinted for Lilac) so a theme only has to
    name a handful of solid colours."""
    return {
        "name": name,
        "bg": bg, "bg_deep": bg_deep, "surface": surface,
        "row_alt": row_alt, "header_bg": header_bg, "code_bg": code_bg,
        "text": text, "text_dim": text_dim, "text_faint": text_faint,
        "accent": accent, "accent_hi": accent_hi, "accent_lo": accent_lo,
        "on_accent": on_accent,
        "border": f"rgba({overlay}, {border_a})",
        "border_strong": f"rgba({overlay}, {border_strong_a})",
        "hover": f"rgba({overlay}, {hover_a})",
        "hover_strong": f"rgba({overlay}, {hover_strong_a})",
        "field": f"rgba({overlay}, {field_a})",
        "scrollbar": f"rgba({overlay}, {scroll_a})",
        "scrollbar_hi": f"rgba({overlay}, {scroll_hi_a})",
        "sel": _rgba(accent, "0.30"),
        "sel_active": _rgba(accent, "0.45"),
        "accent_soft": _rgba(accent, "0.18"),
    }


# ── palettes ──────────────────────────────────────────────────────────────────

_DARK = _theme(
    "Dark",
    bg="#202020", bg_deep="#1a1a1a", surface="#2c2c2c", row_alt="#242424",
    header_bg="#1a1a1a", code_bg="#141414",
    text="#ffffff", text_dim="#9da3ad", text_faint="#6a6f78",
    accent="#0078d4", accent_hi="#2b90e0", accent_lo="#0067c0",
)

_HIGH_CONTRAST = _theme(
    "High Contrast",
    bg="#000000", bg_deep="#000000", surface="#0b0b0b", row_alt="#0e0e0e",
    header_bg="#000000", code_bg="#000000",
    text="#ffffff", text_dim="#e6e6e6", text_faint="#b9b9b9",
    accent="#ffd400", accent_hi="#ffe34d", accent_lo="#e6bf00", on_accent="#000000",
    border_a="0.45", border_strong_a="0.70",
    hover_a="0.16", hover_strong_a="0.26",
    field_a="0.10", scroll_a="0.45", scroll_hi_a="0.75",
)

_LILAC = _theme(
    "Lilac",
    bg="#1b1726", bg_deep="#141019", surface="#271f37", row_alt="#211b2f",
    header_bg="#161121", code_bg="#100c18",
    text="#f3eefc", text_dim="#b9acd6", text_faint="#7e7298",
    accent="#a371f7", accent_hi="#b794f6", accent_lo="#8a55e6",
    overlay="199, 174, 252",
)

THEMES: dict[str, dict[str, str]] = {
    t["name"]: t for t in (_DARK, _HIGH_CONTRAST, _LILAC)
}
DEFAULT_THEME = "Dark"


# ── QSS template ──────────────────────────────────────────────────────────────

_QSS = Template("""
/* ── Base ──────────────────────────────────────────────────────────────── */
* {
    font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
    font-size: 14px;
}
QWidget {
    background-color: ${bg};
    color: ${text};
    selection-background-color: ${accent};
    selection-color: ${on_accent};
}
QMainWindow { background: ${bg_deep}; }
QDialog { background: ${bg}; }

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableView {
    background: ${bg};
    alternate-background-color: ${row_alt};
    border: none;
    outline: 0;
    gridline-color: transparent;
    show-decoration-selected: 1;
}
QTableView::item { padding: 3px 8px; border: none; }
QTableView::item:selected { background: ${sel}; color: ${text}; }
QTableView::item:selected:active { background: ${sel_active}; }
QTableView::item:hover:!selected { background: ${hover}; }

/* ── Header ─────────────────────────────────────────────────────────────── */
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: ${header_bg};
    color: ${text_dim};
    border: none;
    border-right: 1px solid ${border};
    border-bottom: 1px solid ${border_strong};
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
QHeaderView::section:hover { background: ${hover}; color: ${text}; }
QHeaderView::section:last { border-right: none; }
QHeaderView::up-arrow, QHeaderView::down-arrow { width: 8px; height: 8px; }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {
    background: ${field};
    color: ${text};
    border: 1px solid ${border};
    border-radius: 6px;
    padding: 6px 18px;
    min-width: 60px;
}
QPushButton:hover { background: ${hover_strong}; border-color: ${border_strong}; }
QPushButton:pressed { background: ${hover}; }
QPushButton:checked { background: ${accent_lo}; border-color: ${border_strong}; color: ${on_accent}; }
QPushButton:checked:hover { background: ${accent_hi}; }
QPushButton:disabled { color: ${text_faint}; background: ${field}; border-color: ${border}; }

/* ── Input ───────────────────────────────────────────────────────────────── */
QLineEdit {
    background: ${field};
    border: 1px solid ${border};
    border-radius: 6px;
    padding: 6px 12px;
    color: ${text};
}
QLineEdit:hover { background: ${hover_strong}; border-color: ${border_strong}; }
QLineEdit:focus { background: ${hover}; border-color: ${accent}; border-bottom-width: 2px; }
QLineEdit::placeholder { color: ${text_faint}; }

/* ── Tabs ────────────────────────────────────────────────────────────────── */
QTabWidget::pane { border: none; background: transparent; top: -1px; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent;
    color: ${text_dim};
    padding: 10px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: 0;
}
QTabBar::tab:selected { color: ${text}; border-bottom-color: ${accent}; }
QTabBar::tab:hover:!selected { color: ${text}; background: ${hover}; }

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter::handle { background: ${hover}; }
QSplitter::handle:vertical { height: 3px; margin: 1px 0; }
QSplitter::handle:horizontal { width: 3px; margin: 0 1px; }
QSplitter::handle:hover { background: ${accent}; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; border: none; }
QScrollBar::handle:vertical {
    background: ${scrollbar};
    border-radius: 4px;
    min-height: 28px;
    margin: 1px 1px 1px 2px;
}
QScrollBar::handle:vertical:hover  { background: ${scrollbar_hi}; }
QScrollBar::handle:vertical:pressed { background: ${accent}; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; border: none; }
QScrollBar::handle:horizontal {
    background: ${scrollbar};
    border-radius: 4px;
    min-width: 28px;
    margin: 2px 1px 1px 1px;
}
QScrollBar::handle:horizontal:hover  { background: ${scrollbar_hi}; }
QScrollBar::handle:horizontal:pressed { background: ${accent}; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

/* ── Status bar ──────────────────────────────────────────────────────────── */
QStatusBar {
    background: ${bg_deep};
    color: ${text_faint};
    font-size: 12px;
    border-top: 1px solid ${border};
    padding: 0 4px;
}
QStatusBar::item { border: none; }

/* ── Menu ────────────────────────────────────────────────────────────────── */
QMenu {
    background: ${surface};
    border: 1px solid ${border_strong};
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    color: ${text};
    padding: 7px 22px 7px 14px;
    border-radius: 5px;
    margin: 1px 2px;
}
QMenu::item:selected { background: ${hover_strong}; }
QMenu::item:disabled { color: ${text_faint}; }
QMenu::separator { height: 1px; background: ${border_strong}; margin: 4px 8px; }
QMenu::indicator { width: 16px; height: 16px; left: 6px; }

/* ── MenuBar ─────────────────────────────────────────────────────────────── */
QMenuBar {
    background: ${bg_deep};
    color: ${text_dim};
    border-bottom: 1px solid ${border};
    padding: 2px 4px;
}
QMenuBar::item { background: transparent; padding: 6px 12px; border-radius: 5px; margin: 1px; }
QMenuBar::item:selected { background: ${hover_strong}; color: ${text}; }
QMenuBar::item:pressed  { background: ${accent_soft}; color: ${text}; }

/* ── ProgressBar ─────────────────────────────────────────────────────────── */
QProgressBar {
    background: ${field};
    border: 1px solid ${border};
    border-radius: 6px;
    max-height: 6px;
    text-align: center;
}
QProgressBar::chunk { background: ${accent}; border-radius: 6px; }

/* ── GroupBox ────────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid ${border};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -1px;
    color: ${text_dim};
    background: ${bg};
    padding: 0 5px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}

/* ── TextEdit / code areas ───────────────────────────────────────────────── */
QTextEdit {
    background: ${code_bg};
    border: 1px solid ${border};
    border-radius: 5px;
    color: ${text_dim};
    selection-background-color: ${accent};
    selection-color: ${on_accent};
}

/* ── Tooltip ─────────────────────────────────────────────────────────────── */
QToolTip {
    background: ${surface};
    color: ${text};
    border: 1px solid ${border_strong};
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
}

/* ── MessageBox ──────────────────────────────────────────────────────────── */
QMessageBox { background: ${surface}; }
QMessageBox QLabel { color: ${text}; background: transparent; }

/* ── Read-only scan banner (semantic amber, theme-independent) ───────────── */
QLabel#scanBanner {
    background: rgba(240, 160, 0, 0.10);
    color: #f0a000;
    border: 1px solid rgba(240, 160, 0, 0.30);
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}
""")


def stylesheet(name: str = DEFAULT_THEME) -> str:
    """Render the full QSS for the named theme (falls back to the default)."""
    return _QSS.substitute(THEMES.get(name, THEMES[DEFAULT_THEME]))


# Backwards-compatible default stylesheet.
DARK = stylesheet(DEFAULT_THEME)
