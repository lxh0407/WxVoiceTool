import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import ui.main_window as M
from ui.settings_dialog import SettingsDialog


def test_mainwindow_constructs():
    app = QApplication.instance() or QApplication([])
    w = M.MainWindow(auto_start=False)
    assert w.windowTitle() != ""
    assert w.table.columnCount() == 4


def test_settings_dialog_constructs():
    app = QApplication.instance() or QApplication([])
    d = SettingsDialog(None, {"data_root": "", "dll": "", "account_dir": ""})
    cfg = d.result_config()
    assert set(cfg) >= {"data_root", "dll", "account_dir"}
