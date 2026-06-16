"""Programmatic app icon — no external image files needed."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QPainterPath, QLinearGradient,
)


def app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_draw(sz))
    return icon


def _draw(sz: int) -> QPixmap:
    pix = QPixmap(sz, sz)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

    f = sz / 32.0  # everything authored on a 32×32 canvas

    # ── rounded square background ─────────────────────────────────────────
    m = 1.5 * f
    bg = QPainterPath()
    bg.addRoundedRect(m, m, sz - 2 * m, sz - 2 * m, 7 * f, 7 * f)

    grad = QLinearGradient(0.0, 0.0, float(sz), float(sz))
    grad.setColorAt(0.0, QColor("#1e4a9a"))
    grad.setColorAt(1.0, QColor("#0a1829"))
    p.fillPath(bg, grad)

    # ── three process rows (dot + bar) ────────────────────────────────────
    p.setPen(Qt.NoPen)

    dot_r  = 2.2 * f
    bar_h  = 1.9 * f
    dot_x  = 5.5 * f
    bar_x0 = 10.5 * f
    bar_max = sz - bar_x0 - 3.5 * f

    rows = [
        ( 8.0 * f, "#2ecc71", 0.72),
        (16.0 * f, "#60cdff", 0.46),
        (24.0 * f, "#f0a020", 0.88),
    ]

    for cy, color, frac in rows:
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(dot_x, cy), dot_r, dot_r)

        bw = bar_max * frac
        rect = QRectF(bar_x0, cy - bar_h / 2, bw, bar_h)
        bar = QPainterPath()
        bar.addRoundedRect(rect, bar_h / 2, bar_h / 2)
        p.setBrush(QColor(255, 255, 255, 85))
        p.drawPath(bar)

    p.end()
    return pix
