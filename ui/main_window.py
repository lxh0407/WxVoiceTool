import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QProgressBar, QPushButton,
    QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from core import paths
from ui.workers import ExportWorker, PrepareWorker

CHECK_COL, NAME_COL, DUR_COL, CNT_COL = 0, 1, 2, 3


class MainWindow(QMainWindow):
    def __init__(self, auto_start: bool = True):
        super().__init__()
        self.setWindowTitle("微信语音提取器 · WxVoiceTool")
        self.resize(940, 620)
        self._index = []
        self._work = None
        self._account = None
        self._prepare = None
        self._export = None
        self._build_ui()
        if auto_start:
            self._start_prepare()

    # ---------- UI ----------
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        # header
        header = QFrame()
        header.setObjectName("Card")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        title = QLabel("微信语音提取器")
        title.setObjectName("Title")
        self.status = QLabel("启动中…")
        self.status.setObjectName("Sub")
        self.redetect_btn = QPushButton("重新检测")
        self.redetect_btn.clicked.connect(lambda: self._start_prepare())
        hl.addWidget(title)
        hl.addSpacing(10)
        hl.addWidget(self.status, 1)
        hl.addWidget(self.redetect_btn)
        outer.addWidget(header)

        # body
        body = QHBoxLayout()
        body.setSpacing(12)

        left = QFrame()
        left.setObjectName("Card")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 14)
        ll.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索备注名 / wxid…")
        self.search.textChanged.connect(self._filter)
        ll.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["选择", "备注名", "可提取时长", "语音条数"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(NAME_COL, QHeaderView.Stretch)
        self.table.setColumnWidth(CHECK_COL, 50)
        self.table.setColumnWidth(DUR_COL, 110)
        self.table.setColumnWidth(CNT_COL, 90)
        ll.addWidget(self.table, 1)
        row = QHBoxLayout()
        all_btn = QPushButton("全选")
        none_btn = QPushButton("全不选")
        all_btn.clicked.connect(lambda: self._check_all(True))
        none_btn.clicked.connect(lambda: self._check_all(False))
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        row.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("Sub")
        row.addWidget(self.count_label)
        ll.addLayout(row)
        body.addWidget(left, 1)

        right = QFrame()
        right.setObjectName("Card")
        right.setFixedWidth(280)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 14, 14, 14)
        rl.setSpacing(10)

        rl.addWidget(QLabel("目标时长（秒）"))
        self.seconds = QSpinBox()
        self.seconds.setRange(1, 300)
        self.seconds.setValue(10)
        rl.addWidget(self.seconds)

        rl.addWidget(QLabel("输出格式"))
        fmt_row = QHBoxLayout()
        self.wav = QRadioButton("WAV（无损）")
        self.mp3 = QRadioButton("MP3（体积小）")
        self.wav.setChecked(True)
        fmt_row.addWidget(self.wav)
        fmt_row.addWidget(self.mp3)
        rl.addLayout(fmt_row)

        rl.addWidget(QLabel("输出目录"))
        self.out_edit = QLineEdit(str(paths.DEFAULT_OUT_DIR))
        browse = QPushButton("选择…")
        browse.clicked.connect(self._choose_dir)
        orow = QHBoxLayout()
        orow.addWidget(self.out_edit, 1)
        orow.addWidget(browse)
        rl.addLayout(orow)

        self.trim = QCheckBox("裁剪到精确时长")
        self.trim.setChecked(True)
        rl.addWidget(self.trim)

        rl.addStretch(1)
        self.export_btn = QPushButton("开始导出")
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self._start_export)
        self.open_btn = QPushButton("打开输出目录")
        self.open_btn.clicked.connect(self._open_out)
        rl.addWidget(self.export_btn)
        rl.addWidget(self.open_btn)
        body.addWidget(right)

        outer.addLayout(body, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        outer.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(90)
        outer.addWidget(self.log)

    # ---------- logic ----------
    def _append(self, msg: str):
        self.log.append(msg)

    def _set_busy(self, busy: bool):
        self.export_btn.setEnabled(not busy)
        self.redetect_btn.setEnabled(not busy)

    def _start_prepare(self, manual_key: str | None = None):
        if self._prepare and self._prepare.isRunning():
            return
        self._set_busy(True)
        self.progress.setValue(0)
        self.table.setRowCount(0)
        self.status.setText("准备中…")
        self._prepare = PrepareWorker(manual_key)
        self._prepare.progress.connect(self._on_progress)
        self._prepare.done.connect(self._on_prepared)
        self._prepare.failed.connect(self._on_failed)
        self._prepare.start()

    def _on_progress(self, pct: int, text: str):
        self.progress.setValue(pct)
        self.status.setText(text)

    def _on_prepared(self, data: dict):
        self._set_busy(False)
        self._account = data["account"]
        self._work = data["work"]
        self._index = data["index"]
        self.status.setText("账号 %s · %d 位联系人可提取语音" % (self._account.wxid, len(self._index)))
        self._append("密钥来源：%s" % data["key"].source)
        self._populate(self._index)

    def _on_failed(self, msg: str, needs_manual: bool):
        self._set_busy(False)
        self.status.setText("失败")
        self._append("[错误] " + msg)
        if needs_manual:
            text, ok = QInputDialog.getText(self, "手动输入密钥",
                                            "未能自动提取密钥。请粘贴 64 位十六进制密钥：")
            if ok and text.strip():
                self._start_prepare(text.strip())

    def _populate(self, index):
        self.table.setRowCount(0)
        for c in index:
            r = self.table.rowCount()
            self.table.insertRow(r)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(r, CHECK_COL, chk)
            name = QTableWidgetItem(c.name)
            name.setToolTip(c.username)
            name.setData(Qt.UserRole, c.username)
            self.table.setItem(r, NAME_COL, name)
            dur = QTableWidgetItem("%.1f s" % (c.extractable_ms / 1000.0))
            dur.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, DUR_COL, dur)
            cnt = QTableWidgetItem(str(len(c.clips)))
            cnt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, CNT_COL, cnt)
        self._update_count()

    def _filter(self, text: str):
        text = (text or "").strip().lower()
        for r in range(self.table.rowCount()):
            name = self.table.item(r, NAME_COL)
            hay = (name.text() + " " + str(name.data(Qt.UserRole))).lower()
            self.table.setRowHidden(r, bool(text) and text not in hay)

    def _check_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                self.table.item(r, CHECK_COL).setCheckState(state)
        self._update_count()

    def _update_count(self):
        n = sum(1 for r in range(self.table.rowCount())
                if self.table.item(r, CHECK_COL).checkState() == Qt.Checked)
        self.count_label.setText("已选 %d 人" % n)

    def _checked_contacts(self):
        chosen = []
        for r in range(self.table.rowCount()):
            if self.table.item(r, CHECK_COL).checkState() == Qt.Checked:
                u = self.table.item(r, NAME_COL).data(Qt.UserRole)
                chosen.append(next(c for c in self._index if c.username == u))
        return chosen

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def _open_out(self):
        d = self.out_edit.text().strip()
        if d and Path(d).is_dir():
            os.startfile(d)  # noqa: S606
        else:
            self._append("输出目录不存在：" + d)

    def _start_export(self):
        if self._work is None:
            self._append("尚未准备就绪，请等待或点【重新检测】。")
            return
        contacts = self._checked_contacts()
        if not contacts:
            self._append("请先勾选至少一位联系人。")
            return
        fmt = "mp3" if self.mp3.isChecked() else "wav"
        out_dir = self.out_edit.text().strip() or str(paths.DEFAULT_OUT_DIR)
        self._set_busy(True)
        self.progress.setValue(0)
        self._export = ExportWorker(self._work, contacts, self.seconds.value() * 1000,
                                    fmt, out_dir, self.trim.isChecked())
        self._export.progress.connect(self._on_progress)
        self._export.done.connect(self._on_exported)
        self._export.failed.connect(self._on_export_failed)
        self._export.start()

    def _on_exported(self, results):
        self._set_busy(False)
        self.progress.setValue(100)
        self.status.setText("导出完成：%d 个文件" % len(results))
        for p in results:
            self._append("导出 " + str(p))

    def _on_export_failed(self, msg):
        self._set_busy(False)
        self._append("[导出错误] " + msg)
