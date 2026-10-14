import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import ui.main_window as M


def test_mainwindow_constructs():
    app = QApplication.instance() or QApplication([])
    w = M.MainWindow(auto_start=False)
    assert w.windowTitle() != ""
    assert w.table.columnCount() == 4
