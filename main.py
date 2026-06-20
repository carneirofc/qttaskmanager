import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from procman.window import MainWindow
from procman.icon import app_icon


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon = app_icon()
    app.setWindowIcon(icon)

    win = MainWindow(interval_ms=1000)
    win.setWindowIcon(icon)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
