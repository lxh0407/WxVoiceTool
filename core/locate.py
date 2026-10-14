import glob
import os
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None


@dataclass
class Account:
    data_root: Path
    account_dir: Path
    wxid: str


_SUFFIX = re.compile(r"_[0-9a-z]{4}$")
_ABS_PATH = re.compile(r"^[A-Za-z]:\\[^\r\n]+$")


def wxid_from_dirname(name: str) -> str:
    return _SUFFIX.sub("", name)


def find_data_root(appdata: Path | None = None) -> Path | None:
    if appdata is None:
        appdata = Path(os.environ.get("APPDATA", ""))
    cfg_dir = appdata / "Tencent" / "xwechat" / "config"
    candidates: list[Path] = []
    if cfg_dir.is_dir():
        for ini in cfg_dir.glob("*.ini"):
            try:
                text = ini.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                line = line.strip().strip('"')
                if _ABS_PATH.match(line):
                    candidates.append(Path(line) / "xwechat_files")
    for cand in candidates:
        if cand.is_dir():
            return cand
    if candidates:
        return candidates[0]
    for fallback in (Path.home() / "Documents" / "xwechat_files",):
        if fallback.is_dir():
            return fallback
    return None


def find_weixin_dll() -> str | None:
    cands: list[str] = []
    if winreg is not None:
        for hive, sub in ((winreg.HKEY_CURRENT_USER, r"Software\Tencent\Weixin"),
                          (winreg.HKEY_LOCAL_MACHINE, r"Software\Tencent\Weixin"),
                          (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Tencent\Weixin")):
            try:
                with winreg.OpenKey(hive, sub) as k:
                    install, _ = winreg.QueryValueEx(k, "InstallPath")
                    cands += glob.glob(os.path.join(install, "*", "Weixin.dll"))
            except OSError:
                pass
    for base in (r"C:\Program Files\Tencent\Weixin", r"C:\Program Files (x86)\Tencent\Weixin"):
        cands += glob.glob(os.path.join(base, "*", "Weixin.dll"))
    for drive in ("D:", "E:", "F:", "G:"):
        cands += glob.glob(os.path.join(drive + "\\", "Program Files*", "Tencent", "Weixin", "*", "Weixin.dll"))
    cands = [c for c in cands if os.path.isfile(c)]
    return sorted(cands)[-1] if cands else None


def find_accounts(data_root: Path) -> list[Account]:
    accounts: list[Account] = []
    if not data_root.is_dir():
        return accounts
    for child in sorted(data_root.iterdir()):
        if not child.is_dir() or child.name in ("all_users", "Backup"):
            continue
        if not (child / "db_storage").is_dir():
            continue
        accounts.append(Account(data_root=data_root, account_dir=child, wxid=wxid_from_dirname(child.name)))
    return accounts
