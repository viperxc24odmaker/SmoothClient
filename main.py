"""Smooth Client Launcher entry point."""
import sys

from PyQt6.QtWidgets import QApplication

from smoothlauncher import config
from ui.main_window import MainWindow


def main() -> int:
    config.ensure_dirs()
    app = QApplication(sys.argv)
    app.setApplicationName("Smooth Client Launcher")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
