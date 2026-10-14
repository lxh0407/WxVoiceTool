import sys

from PySide6.QtWidgets import QApplication

from core import paths
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    qss = paths.APP_DIR / "ui" / "theme.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
