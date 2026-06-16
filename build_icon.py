"""Generate app.ico from programmatic icon — run once before pyside6-deploy."""
import sys
from PySide6.QtWidgets import QApplication
from procman.icon import _draw

app = QApplication(sys.argv)

sizes = [16, 24, 32, 48, 64, 128, 256]
pixmaps = [_draw(sz) for sz in sizes]
# Save largest as base; Qt can save .ico with multiple sizes via QIcon trick,
# but simplest is to save the 256px pixmap — Windows scales it.
pixmaps[-1].save("app.ico", "ICO")
print("app.ico written")
