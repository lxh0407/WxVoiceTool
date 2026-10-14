import os
import sqlite3
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core import dbdecrypt, keyfinder, locate, paths, silk, voiceexport, voiceindex


class PrepareWorker(QThread):
    progress = Signal(int, str)
    done = Signal(object)
    failed = Signal(str, bool)

    def __init__(self, manual_key: str | None = None, settings: dict | None = None):
        super().__init__()
        self.manual_key = manual_key
        self.settings = settings or {}

    def _resolve(self):
        root = None
        cfg_root = self.settings.get("data_root")
        if cfg_root and Path(cfg_root).is_dir():
            root = Path(cfg_root)
        if root is None:
            root = locate.find_data_root()
        if root is None:
            raise RuntimeError("未找到微信数据目录（xwechat_files）。请在【设置】中手动指定。")
        accounts = locate.find_accounts(root)
        if not accounts:
            raise RuntimeError("该数据目录下未找到微信账号（含 db_storage 的目录）。请在【设置】中检查。")
        cfg_acc = self.settings.get("account_dir")
        acc = None
        if cfg_acc:
            acc = next((a for a in accounts if str(a.account_dir) == cfg_acc), None)
        if acc is None:
            acc = accounts[0]
        dll = self.settings.get("dll")
        if not (dll and os.path.isfile(dll)):
            dll = locate.find_weixin_dll()
        return root, accounts, acc, dll

    def run(self):
        try:
            paths.ensure_dirs()
            self.progress.emit(2, "定位微信数据目录…")
            root, accounts, acc, dll = self._resolve()
            if len(accounts) > 1:
                self.progress.emit(4, "检测到 %d 个账号，已选 %s（可在【设置】中切换）" % (len(accounts), acc.wxid))
            session_db = acc.account_dir / "db_storage" / "session" / "session.db"

            key = None
            if self.manual_key:
                key = keyfinder.parse_manual_key(self.manual_key, acc.wxid)
            else:
                cache = keyfinder.load_cache()
                if cache and cache.get("account") == acc.wxid:
                    key = keyfinder.KeyResult(cache["passphrase_hex"], cache["account"],
                                              cache.get("version", ""), "cache")
                    self.progress.emit(10, "使用已缓存密钥")
            if key is None:
                if not dll:
                    self.failed.emit(
                        "未找到 Weixin.dll（自动定位失败）。请在【设置】中指定，或手动粘贴 64 位密钥。", True)
                    return
                self.progress.emit(15, "正在提取密钥（读取微信进程内存）…")
                key = keyfinder.recover_key(
                    acc, dll, session_db,
                    progress=lambda i, n: self.progress.emit(
                        15 + int(20 * i / max(n, 1)), "扫描进程 %d/%d" % (i + 1, n)))
                if key is None:
                    self.failed.emit("未能提取密钥（微信版本特征可能已变化）。可在【设置】中手动粘贴 64 位密钥。", True)
                    return
                keyfinder.save_cache(key)

            pp = bytes.fromhex(key.passphrase_hex)
            self.progress.emit(38, "解密数据库…")
            ds = acc.account_dir / "db_storage"
            work = paths.WORK_DIR / acc.wxid
            work.mkdir(parents=True, exist_ok=True)
            mapping = [("contact/contact.db", "contact.db"),
                       ("message/media_0.db", "media_0.db"),
                       ("message/message_0.db", "message_0.db")]
            for i, (rel, name) in enumerate(mapping):
                dbdecrypt.decrypt_db(ds / rel, work / name, pp)
                self.progress.emit(38 + int((i + 1) / len(mapping) * 34), "解密 " + name)

            self.progress.emit(78, "扫描语音消息…")
            idx = voiceindex.build_index(work / "message_0.db", work / "media_0.db",
                                         work / "contact.db", acc.wxid)
            self.progress.emit(100, "完成：%d 位联系人可提取语音" % len(idx))
            self.done.emit({"account": acc, "key": key, "work": work, "index": idx})
        except Exception as e:
            self.failed.emit(str(e), False)


class ExportWorker(QThread):
    progress = Signal(int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, work, contacts, target_ms, fmt, out_dir, trim=True):
        super().__init__()
        self.work = work
        self.contacts = contacts
        self.target_ms = target_ms
        self.fmt = fmt
        self.out_dir = out_dir
        self.trim = trim

    def run(self):
        try:
            med = sqlite3.connect(str(self.work / "media_0.db"))
            all_voice = dict(med.execute("SELECT svr_id, voice_data FROM VoiceInfo"))
            med.close()
            results = []
            n = max(len(self.contacts), 1)
            for i, c in enumerate(self.contacts):
                vmap = {cl.server_id: all_voice[cl.server_id]
                        for cl in c.clips if cl.server_id in all_voice}
                p = voiceexport.export_contact(c, vmap, self.target_ms, self.fmt,
                                               self.out_dir, silk.decode_silk, self.trim)
                results.append(p)
                self.progress.emit(int((i + 1) / n * 100), "已导出 %s" % c.name)
            self.done.emit(results)
        except Exception as e:
            self.failed.emit(str(e))
