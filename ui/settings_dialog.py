from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from core import locate, settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None, current: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(580, 280)
        current = current or {}
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("微信数据目录（选择 xwechat_files 文件夹）"))
        row = QHBoxLayout()
        self.root_edit = QLineEdit(current.get("data_root", ""))
        b1 = QPushButton("选择…")
        b1.clicked.connect(self._pick_root)
        row.addWidget(self.root_edit, 1)
        row.addWidget(b1)
        layout.addLayout(row)

        layout.addWidget(QLabel("Weixin.dll 路径（用于提取密钥）"))
        row2 = QHBoxLayout()
        self.dll_edit = QLineEdit(current.get("dll", ""))
        b2 = QPushButton("选择…")
        b2.clicked.connect(self._pick_dll)
        row2.addWidget(self.dll_edit, 1)
        row2.addWidget(b2)
        layout.addLayout(row2)

        layout.addWidget(QLabel("账号"))
        self.account = QComboBox()
        layout.addWidget(self.account)

        hint = QLabel("留空则自动探测；填了但无效会自动回退。")
        hint.setObjectName("Sub")
        layout.addWidget(hint)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

        self._populate_accounts(current.get("account_dir", ""))
        self.root_edit.editingFinished.connect(self._populate_accounts)

    def _pick_root(self):
        d = QFileDialog.getExistingDirectory(self, "选择 xwechat_files 目录",
                                             self.root_edit.text() or str(Path.home()))
        if d:
            self.root_edit.setText(d)
            self._populate_accounts()

    def _pick_dll(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择 Weixin.dll", self.dll_edit.text() or "",
                                           "Weixin.dll (Weixin.dll);;DLL (*.dll)")
        if f:
            self.dll_edit.setText(f)

    def _populate_accounts(self, want=None):
        self.account.clear()
        self.account.addItem("（自动 / 第一个）", "")
        root = self.root_edit.text().strip()
        if root and Path(root).is_dir():
            for a in locate.find_accounts(Path(root)):
                self.account.addItem("%s  (%s)" % (a.wxid, a.account_dir.name), str(a.account_dir))
        if want:
            idx = self.account.findData(want)
            if idx >= 0:
                self.account.setCurrentIndex(idx)

    def result_config(self) -> dict:
        cfg = dict(settings.load())
        cfg["data_root"] = self.root_edit.text().strip()
        cfg["dll"] = self.dll_edit.text().strip()
        cfg["account_dir"] = self.account.currentData() or ""
        return cfg
