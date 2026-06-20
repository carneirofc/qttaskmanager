"""Theming — a Fluent-inspired QSS template rendered against a palette.

The stylesheet lives in ``styles/app.qss`` (bundled as package data) authored
as a string.Template, so CSS braces pass through untouched and only ``${name}``
slots are substituted. Each palette fills those slots, giving several selectable
themes that can be swapped live via ``QApplication.setStyleSheet(stylesheet(name))``.
"""
from __future__ import annotations

from importlib import resources
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

# Lilac — high-contrast: near-black violet base, white text, vivid lilac accent
# and strong borders/dividers.
_LILAC = _theme(
    "Lilac",
    bg="#150f1e", bg_deep="#0c0812", surface="#241934", row_alt="#1d1429",
    header_bg="#0f0a17", code_bg="#0a0710",
    text="#ffffff", text_dim="#d4c6f2", text_faint="#9a86c0",
    accent="#b388ff", accent_hi="#cba6ff", accent_lo="#9a5cf6", on_accent="#1a0d2e",
    overlay="206, 178, 255",
    border_a="0.22", border_strong_a="0.36",
    hover_a="0.12", hover_strong_a="0.22",
    field_a="0.09", scroll_a="0.32", scroll_hi_a="0.52",
)

THEMES: dict[str, dict[str, str]] = {
    t["name"]: t for t in (_DARK, _HIGH_CONTRAST, _LILAC)
}
DEFAULT_THEME = "Dark"


# ── QSS template (loaded from bundled package data) ───────────────────────────

def _load_template() -> Template:
    text = (resources.files(__package__) / "styles" / "app.qss").read_text(encoding="utf-8")
    return Template(text)


_QSS = _load_template()


def stylesheet(name: str = DEFAULT_THEME) -> str:
    """Render the full QSS for the named theme (falls back to the default)."""
    return _QSS.substitute(THEMES.get(name, THEMES[DEFAULT_THEME]))


# Backwards-compatible default stylesheet.
DARK = stylesheet(DEFAULT_THEME)
