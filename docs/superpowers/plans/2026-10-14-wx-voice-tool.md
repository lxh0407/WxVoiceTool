# WxVoiceTool 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个自包含的 Windows GUI 工具，从本机微信 4.x 按联系人提取语音并导出为 WAV/MP3。

**Architecture:** core（纯逻辑，无 UI 依赖）负责定位/取密钥/解密/索引/导出；ui（PySide6）只做展示与编排；SILK 解码通过内置 Node 运行时调用 silk-wasm。所有耗时操作在 QThread 后台执行。

**Tech Stack:** Python 3.13、PySide6、pycryptodome、zstandard、pefile、yara-python、pymem、lameenc、PyInstaller；内置 node.exe + silk-wasm。

**Spec:** `docs/superpowers/specs/2026-10-14-wx-voice-tool-design.md`

## Global Constraints

- 仅 Windows；Python 3.13；GUI 用 PySide6。
- 目标机不依赖安装 Python/Node（Node 运行时随包内置）。
- **绝不写微信数据目录**：对微信库只读；解密产物仅写 `%LOCALAPPDATA%\WxVoiceTool\work\`。
- 只处理 `local_type=34` 语音；排除 `my_wxid` 自己发的；只导 `voice_data` 存在的。
- 采样率固定 24000Hz，PCM 16bit 单声道。
- 密钥缓存文件：`%LOCALAPPDATA%\WxVoiceTool\key.json`。

## Review Focus

- **微信未运行/未登录**：取密钥应给出明确提示而非崩溃或静默失败。
- **微信版本特征变化**：静态/内存特征不匹配时应提示并允许手动粘贴 key。
- **数据库被微信占用/半写**：读库失败要按库降级并提示，不整体崩溃。
- **超大消息库**：`message_0.db` 可达数百 MB，扫描期间 UI 必须保持响应、显示进度。
- **SILK 片段异常/空数据**：单条解码失败应跳过该条并记录，不中断整人导出。

---

### Task 1: 项目骨架、路径与配置

**Files:**
- Create: `requirements.txt`, `core/__init__.py`, `core/paths.py`, `tests/test_paths.py`, `pytest.ini`

**Interfaces:**
- Produces: `core/paths.py` → `APP_DIR: Path`、`USER_DIR: Path`、`WORK_DIR: Path`、`CACHE_FILE: Path`、`LOG_DIR: Path`、`DEFAULT_OUT_DIR: Path`、`ensure_dirs() -> None`。

- [ ] **Step 1: 写失败测试** `tests/test_paths.py`

```python
import core.paths as p
def test_user_dir_under_localappdata():
    assert "WxVoiceTool" in str(p.USER_DIR)
def test_work_and_cache_paths_consistent():
    assert p.CACHE_FILE.parent == p.USER_DIR
    assert p.WORK_DIR.parent == p.USER_DIR
def test_ensure_dirs_creates(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "USER_DIR", tmp_path / "WxVoiceTool")
    monkeypatch.setattr(p, "WORK_DIR", p.USER_DIR / "work")
    monkeypatch.setattr(p, "LOG_DIR", p.USER_DIR / "logs")
    p.ensure_dirs()
    assert p.WORK_DIR.is_dir() and p.LOG_DIR.is_dir()
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_paths.py -v` → FAIL（ModuleNotFoundError）。

- [ ] **Step 3: 实现** `core/paths.py`

`USER_DIR = Path(os.environ["LOCALAPPDATA"]) / "WxVoiceTool"`；`WORK_DIR=USER_DIR/"work"`；`CACHE_FILE=USER_DIR/"key.json"`；`LOG_DIR=USER_DIR/"logs"`；`DEFAULT_OUT_DIR=Path.home()/"WxVoiceSamples"`；`APP_DIR=Path(__file__).resolve().parent.parent`。`ensure_dirs()` 用 `mkdir(parents=True, exist_ok=True)`。`requirements.txt` 写：`PySide6` `pycryptodome` `zstandard` `pefile` `yara-python` `pymem` `lameenc` `pytest`。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_paths.py -v` → PASS。

- [ ] **Step 5: 提交**：`git init`（若未初始化）后 `git add -A && git commit -m "chore: project scaffold and paths"`。

---

### Task 2: 定位微信数据目录与账号

**Files:**
- Create: `core/locate.py`, `tests/test_locate.py`

**Interfaces:**
- Produces: `@dataclass Account(data_root: Path, account_dir: Path, wxid: str)`；`find_data_root(appdata: Path|None=None) -> Path|None`；`find_accounts(data_root: Path) -> list[Account]`；`wxid_from_dirname(name: str) -> str`（去掉结尾 `_xxxx` 后缀）。

- [ ] **Step 1: 写失败测试** `tests/test_locate.py`

```python
from pathlib import Path
import core.locate as L
def test_wxid_from_dirname_strips_suffix():
    assert L.wxid_from_dirname("wxid_jng2lqldeiag21_23b7") == "wxid_jng2lqldeiag21"
    assert L.wxid_from_dirname("zitang90") == "zitang90"
def test_find_data_root_reads_ini(tmp_path):
    cfg = tmp_path / "Tencent" / "xwechat" / "config"; cfg.mkdir(parents=True)
    (cfg / "a.ini").write_text("E:\\WX\\Documents\n", encoding="utf-8")
    assert L.find_data_root(appdata=tmp_path) == Path("E:\\WX\\Documents") / "xwechat_files"
def test_find_accounts_lists_dirs(tmp_path):
    (tmp_path / "all_users").mkdir()
    (tmp_path / "wxid_a_1234").mkdir()
    accts = L.find_accounts(tmp_path)
    assert [a.wxid for a in accts] == ["wxid_a"]
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_locate.py -v` → FAIL。

- [ ] **Step 3: 实现** `core/locate.py`

`find_data_root`：遍历 `appdata/"Tencent"/"xwechat"/"config"` 下 `*.ini`，逐行找「像绝对路径的字符串」，取第一个，拼 `/ "xwechat_files"`；都无则回退候选 `~/Documents/xwechat_files`。`find_accounts`：枚举 `data_root.iterdir()`，跳过 `all_users`/`Backup`，保留含 `db_storage` 的目录。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_locate.py -v` → PASS。

- [ ] **Step 5: 提交**：`git commit -am "feat: locate wechat data root and accounts"`。

---

### Task 3: 数据库解密

**Files:**
- Create: `core/dbdecrypt.py`, `tests/test_dbdecrypt.py`

**Interfaces:**
- Produces: `PAGE=4096`、`RESERVE=80`、`IV_SZ=16`；`make_enc_key(passphrase: bytes, salt: bytes) -> bytes`；`decrypt_page1(page: bytes, enc_key: bytes) -> bytes`（返回重组的明文首页，前 16 字节为 `b"SQLite format 3\x00"`）；`decrypt_db(src: Path, dst: Path, passphrase: bytes) -> None`。

- [ ] **Step 1: 写失败测试** `tests/test_dbdecrypt.py`（自造一页做加解密对照）

```python
import os
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA512
import core.dbdecrypt as D

def _make_fake_page(passphrase, salt):
    enc = D.make_enc_key(passphrase, salt)
    plain = b"SQLite format 3\x00" + os.urandom(D.PAGE - 16 - D.RESERVE) + b"\x50" * D.RESERVE
    iv = os.urandom(16)
    ct = AES.new(enc, AES.MODE_CBC, iv).encrypt(plain[16:D.PAGE - D.RESERVE])
    return salt + ct + iv + b"\x00" * (D.RESERVE - 16)

def test_decrypt_page1_recovers_header():
    salt = os.urandom(16); pp = os.urandom(32)
    page = _make_fake_page(pp, salt)
    out = D.decrypt_page1(page, D.make_enc_key(pp, salt))
    assert out[:16] == b"SQLite format 3\x00"

def test_make_enc_key_uses_pbkdf2_sha512():
    from Crypto.Protocol.KDF import PBKDF2 as P
    from Crypto.Hash import SHA512 as S
    assert D.make_enc_key(b"a" * 32, b"s" * 16) == P(b"a" * 32, b"s" * 16, dkLen=32, count=256000, hmac_hash_module=S)
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_dbdecrypt.py -v` → FAIL。

- [ ] **Step 3: 实现** `core/dbdecrypt.py`

`make_enc_key` = `PBKDF2(passphrase, salt, dkLen=32, count=256000, hmac_hash_module=SHA512)`。`decrypt_page1`：`iv=page[PAGE-RESERVE:PAGE-RESERVE+16]`、`ct=page[16:PAGE-RESERVE]`、`pt=AES-CBC(enc,iv).decrypt(ct)`，返回 `b"SQLite format 3\x00" + pt + b"\x00"*RESERVE`。`decrypt_db`：首页走 `decrypt_page1`；其余页 `ct=page[0:PAGE-RESERVE]`、同样取尾部 IV，`pt` 后补 `RESERVE` 个 0；末页按 16 对齐截断。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_dbdecrypt.py -v` → PASS。

- [ ] **Step 5: 集成冒烟（本机有真实微信时）**：对真实 `session.db` 用已取密钥解密，`sqlite3` 能 `SELECT name FROM sqlite_master LIMIT 1`。

- [ ] **Step 6: 提交**：`git commit -am "feat: sqlcipher page decryption"`。

---

### Task 4: 取密钥（静态 + 内存 + 校验 + 缓存）

**Files:**
- Create: `core/keyfinder.py`, `tests/test_keyfinder.py`

**Interfaces:**
- Produces: `@dataclass KeyResult(passphrase_hex: str, account: str, version: str, source: str)`；`parse_manual_key(text: str, account: str) -> KeyResult`（校验 64 hex）；`xor_raw(raw: bytes, xor_key: bytes) -> bytes`；`validate(raw: bytes, xor_key: bytes, db_path: Path) -> bytes|None`（返回 passphrase 或 None）；`static_xor_keys(dll: Path) -> list[bytes]`；`find_pid(proc_name="Weixin.exe") -> int|None`；`raw_candidates(pid: int) -> list[bytes]`；`recover_key(account_dir: Path, dll: Path, db_path: Path, progress=None) -> KeyResult|None`；`load_cache()/save_cache(KeyResult)`。

- [ ] **Step 1: 写失败测试** `tests/test_keyfinder.py`

```python
import core.keyfinder as K
def test_xor_raw():
    assert K.xor_raw(bytes([1,2,3]), bytes([1,1,1])) == bytes([0,3,2])
def test_parse_manual_key_valid():
    r = K.parse_manual_key("AB"*32, "wxid_a")
    assert r.passphrase_hex == "ab"*32 and r.source == "manual"
def test_parse_manual_key_invalid():
    import pytest
    with pytest.raises(ValueError):
        K.parse_manual_key("xyz", "wxid_a")
def test_validate_rejects_bad_key(tmp_path):
    # 造一个假库首页，用错的 key 必返回 None
    import os, core.dbdecrypt as D
    salt=os.urandom(16); page=salt+os.urandom(4096-16)
    (tmp_path/"x.db").write_bytes(page)
    assert K.validate(os.urandom(32), os.urandom(32), tmp_path/"x.db") is None
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_keyfinder.py -v` → FAIL。

- [ ] **Step 3: 实现** `core/keyfinder.py`

- `validate`：读库首页；`mac_salt = bytes(b ^ 0x3a for b in salt)`；`pp = xor_raw(raw, xor_key)`；`enc = make_enc_key(pp, salt)`；`mac_key = PBKDF2(enc, mac_salt, dkLen=32, count=2, hmac_hash_module=SHA512)`；`mac = HMAC-SHA512(mac_key, page[16:PAGE-RESERVE+16])` 再 `update(struct.pack('<I',1))`；与 `page[PAGE-RESERVE+16:PAGE]` 比较，相等返回 `pp` 否则 None。
- `static_xor_keys`：读 DLL 字节，用正则 `\x48\xBA(.{8}).{3,8}?\x48\xBA(.{8}).{3,8}?\x48\xBA(.{8}).{3,8}?\x48\xBA(.{8}).{3,8}?\x48\x85\xC0`（DOTALL）搜，拼 4 组 8 字节。
- `raw_candidates`：`OpenProcess` 后 `VirtualQueryEx` 枚举可读私有页，匹配结构体特征 `??????` + `00`*10 + `20 00 00 00 00 00 00 00` + `2f 00 00 00 00 00 00 00`，读该处 8 字节为指针，再读 32 字节；去重后按 `is_potential_key`（相异字节≥15、可打印≤24）过滤。
- `recover_key`：`find_pid`→`static_xor_keys`→`raw_candidates`→对每个 (raw,xor) `validate`，命中即 `KeyResult(passphrase_hex=pp.hex(), version=.., source="memory")`。
- `load_cache/save_cache`：`paths.CACHE_FILE` JSON。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_keyfinder.py -v` → PASS。

- [ ] **Step 5: 集成冒烟（微信运行时）**：`recover_key` 得到 passphrase，`validate` 通过，缓存写入。

- [ ] **Step 6: 提交**：`git commit -am "feat: wechat db key recovery with cache"`。

---

### Task 5: SILK 解码桥（Node）

**Files:**
- Create: `core/silk.py`, `runtime/decode_silk.js`, `tests/test_silk.py`

**Interfaces:**
- Produces: `decode_silk(silk_bytes: bytes, node_exe: Path, script: Path, sample_rate: int=24000) -> bytes`（pcm_s16le）；`pcm_to_wav(pcm: bytes, sample_rate: int=24000) -> bytes`。

- [ ] **Step 1: 写失败测试** `tests/test_silk.py`

```python
import struct, core.silk as S
def test_pcm_to_wav_header():
    wav = S.pcm_to_wav(b"\x00\x00" * 100, 24000)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert struct.unpack("<I", wav[24:28])[0] == 24000
    assert struct.unpack("<H", wav[22:24])[0] == 1
    assert struct.unpack("<I", wav[40:44])[0] == 200
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_silk.py -v` → FAIL。

- [ ] **Step 3: 实现** `core/silk.py` 与 `runtime/decode_silk.js`

`decode_silk`：把 silk 写临时文件，`subprocess.run([node_exe, script, tmp, str(sample_rate)], capture_output)`，脚本将解码后的 PCM 写到 `tmp + ".pcm"`，Python 读回。`pcm_to_wav`：标准 44 字节头（PCM/1ch/16bit）。`decode_silk.js`：`silk-wasm.decode(buf, sr)` → 写 `pcm` 到 `<arg>.pcm`。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_silk.py -v` → PASS。

- [ ] **Step 5: 集成冒烟**：用一条真实 `.silk` 解码，`len(pcm) > 0`。

- [ ] **Step 6: 提交**：`git commit -am "feat: silk decode bridge via node"`。

---

### Task 6: 语音索引（扫库汇总）

**Files:**
- Create: `core/voiceindex.py`, `tests/test_voiceindex.py`

**Interfaces:**
- Produces: `@dataclass VoiceClip(server_id: int, create_time: int, length_ms: int)`；`@dataclass ContactVoices(username: str, name: str, clips: list[VoiceClip], total_ms: int, extractable_ms: int)`；`extract_voicelength(content: bytes) -> int|None`（zstd 解压 + 正则）；`build_index(message_db: Path, media_db: Path, contact_db: Path, my_wxid: str) -> list[ContactVoices]`（按时长降序）。

- [ ] **Step 1: 写失败测试** `tests/test_voiceindex.py`（内存库构造）

```python
import sqlite3, zstandard as zstd, core.voiceindex as V
def _z(b): return zstd.ZstdCompressor().compress(b)
def test_extract_voicelength():
    xml = b'wxid_a:\n<msg><voicemsg voicelength="6480" length="12627" voiceformat="4"/></msg>'
    assert V.extract_voicelength(_z(xml)) == 6480
    assert V.extract_voicelength(b"no voice here") is None
def test_build_index_filters_self_and_missing(tmp_path):
    msg = sqlite3.connect(tmp_path/"m.db")
    msg.execute("CREATE TABLE Name2Id(user_name TEXT PRIMARY KEY, is_session INTEGER)")
    msg.execute("INSERT INTO Name2Id VALUES('wxid_a',0)"); msg.execute("INSERT INTO Name2Id VALUES('wxid_me',0)")
    msg.execute("CREATE TABLE Msg_x(local_id INTEGER, server_id INTEGER, local_type INTEGER, real_sender_id INTEGER, create_time INTEGER, message_content TEXT)")
    # rowid: 1=wxid_a, 2=wxid_me
    xml = b'<msg><voicemsg voicelength="12000" length="10" voiceformat="4"/></msg>'
    msg.execute("INSERT INTO Msg_x VALUES(1,100,34,1,1,?)", (_z(xml),))
    msg.execute("INSERT INTO Msg_x VALUES(2,101,34,2,2,?)", (_z(xml),))   # self, skip
    msg.execute("INSERT INTO Msg_x VALUES(3,102,34,1,3,?)", (_z(xml),))   # svr not in media, no extract
    msg.commit()
    med = sqlite3.connect(tmp_path/"v.db")
    med.execute("CREATE TABLE VoiceInfo(chat_name_id INTEGER, create_time INTEGER, local_id INTEGER, svr_id INTEGER, voice_data BLOB, data_index TEXT)")
    med.execute("INSERT INTO VoiceInfo VALUES(1,1,1,100,?, '0')", (b"\x02#!SILK_V3"+b"0"*20,))
    med.commit()
    con = sqlite3.connect(tmp_path/"c.db")
    con.execute("CREATE TABLE contact(id INTEGER, username TEXT, local_type INTEGER, alias TEXT, nick_name TEXT, remark TEXT)")
    con.execute("INSERT INTO contact VALUES(1,'wxid_a',1,'','小A','阿A')"); con.commit()
    res = V.build_index(tmp_path/"m.db", tmp_path/"v.db", tmp_path/"c.db", "wxid_me")
    assert len(res) == 1
    c = res[0]
    assert c.username == "wxid_a" and c.name == "阿A"
    assert c.total_ms == 24000 and c.extractable_ms == 12000
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_voiceindex.py -v` → FAIL。

- [ ] **Step 3: 实现** `core/voiceindex.py`

`extract_voicelength`：`b[:4]==b"\x28\xb5\x2f\xfd"` 则 zstd 解压；`re.search(rb'voicelength="(\d+)"', data)`。`build_index`：载入 `Name2Id`→rowid→username；载入 `VoiceInfo`→`svr_id`→bool(有数据)；遍历所有 `Msg_%` 表 `local_type=34`，按 `real_sender_id` 归 sender，跳过 `my_wxid`；`name` 取 contact 的 `remark or nick_name or alias or username`；聚合 `total_ms`（全部）与 `extractable_ms`（svr 有数据）。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_voiceindex.py -v` → PASS。

- [ ] **Step 5: 提交**：`git commit -am "feat: voice index builder"`。

---

### Task 7: 导出（选段 + 拼接 + WAV/MP3）

**Files:**
- Create: `core/voiceexport.py`, `tests/test_voiceexport.py`

**Interfaces:**
- Consumes: `VoiceClip`（Task 6）、`decode_silk`/`pcm_to_wav`（Task 5）。
- Produces: `select_clips(clips: list[VoiceClip], target_ms: int) -> list[VoiceClip]`（按 create_time 排序累积到 ≥ target）；`encode_mp3(pcm: bytes, sample_rate: int) -> bytes`；`export_contact(contact: ContactVoices, voice_map: dict[int, bytes], target_ms: int, fmt: str, out_dir: Path, decode) -> Path`。

- [ ] **Step 1: 写失败测试** `tests/test_voiceexport.py`

```python
import core.voiceexport as E
from core.voiceindex import VoiceClip, ContactVoices
def test_select_clips_accumulates_to_target():
    clips=[VoiceClip(1,10,4000),VoiceClip(2,20,7000),VoiceClip(3,30,9000)]
    sel=E.select_clips(clips,10000)
    assert [c.server_id for c in sel]==[1,2]      # 4000->11000>=10000
def test_select_clips_all_if_short():
    clips=[VoiceClip(1,10,3000)]
    assert len(E.select_clips(clips,10000))==1
def test_export_contact_writes_wav(tmp_path):
    def fake_decode(b): return b"\x01\x02"*100
    c=ContactVoices("wxid_a","A",[VoiceClip(1,1,1000)],1000,1000)
    out=E.export_contact(c,{1:b"silk"},1000,"wav",tmp_path,fake_decode)
    assert out.suffix==".wav" and out.read_bytes()[:4]==b"RIFF"
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_voiceexport.py -v` → FAIL。

- [ ] **Step 3: 实现** `core/voiceexport.py`

`select_clips`：`sorted(clips, key=create_time)`，累积 `length_ms` 到 ≥ target。`encode_mp3`：`lameenc.Encoder()`（24000Hz、mono、16bit）`set_bit_rate(64)`，`pcm` 转 Int16 buffer 后 `encode`。`export_contact`：对选中片段 `decode(voice_map[sid])` 拼 PCM；`fmt=="mp3"` 写 mp3 否则 `pcm_to_wav` 写 wav；文件名 `<safe(name)>_<username>.<ext>`。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_voiceexport.py -v` → PASS。

- [ ] **Step 5: 提交**：`git commit -am "feat: voice export wav/mp3"`。

---

### Task 8: GUI（PySide6 主窗口 + 后台线程）

**Files:**
- Create: `ui/__init__.py`, `ui/theme.qss`, `ui/workers.py`, `ui/main_window.py`, `app.py`, `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: Task 2–7 的公开函数。
- Produces: `app.py` `main()` 启动 `MainWindow`；`ui/workers.py`：`RecoverWorker(QThread)`、`IndexWorker(QThread)`、`ExportWorker(QThread)`，各自 `signal`（`progress(int)`, `done(object)`, `failed(str)`）。

- [ ] **Step 1: 写失败测试** `tests/test_ui_smoke.py`

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
import ui.main_window as M
def test_mainwindow_constructs():
    app = QApplication.instance() or QApplication([])
    w = M.MainWindow()
    assert w.windowTitle() != ""
```

- [ ] **Step 2: 运行确认失败**：`python -m pytest tests/test_ui_smoke.py -v` → FAIL。

- [ ] **Step 3: 实现**

- `ui/theme.qss`：深色扁平（背景 `#1e1f26`、卡片 `#2a2c36`、主色 `#4c8bf5`、圆角 8、控件间距 8、表头/行 hover 样式）。
- `ui/workers.py`：三个 QThread，`run()` 里调 core 并在关键节点 `progress.emit`；异常 `failed.emit(str(e))`。
- `ui/main_window.py`：顶栏（账号/状态/【重新检测】）；中央 `QTableWidget`（勾选/备注名/总时长/条数）+ 搜索框 + 全选/反选；参数区（`QSpinBox` 时长默认 10、`QRadioButton` WAV/MP3、`QLineEdit`+选择按钮 输出目录默认 `DEFAULT_OUT_DIR`）；底部 `QProgressBar` + 只读日志 `QTextEdit`；按钮【开始导出】【打开输出目录】【退出】。启动即异步定位+取密钥，完成后 `IndexWorker` 填表。
- `app.py`：`QApplication` → 载入 qss → `MainWindow.show()`。

- [ ] **Step 4: 运行确认通过**：`python -m pytest tests/test_ui_smoke.py -v` → PASS（offscreen）。

- [ ] **Step 5: 手动验收**：`python app.py` → 列出联系人，勾选「崔琪」，选 10s/WAV → 导出，播放核对；再测多人 + MP3。

- [ ] **Step 6: 提交**：`git commit -am "feat: PySide6 GUI and background workers"`。

---

### Task 9: 打包为独立 exe

**Files:**
- Create: `build.spec`, `runtime/node/*`（内置 node.exe 与 `node_modules/silk-wasm`）, `README.md`

**Interfaces:**
- Produces: `dist/WxVoiceTool/WxVoiceTool.exe`（onedir）；`core/silk.py` 运行时用 `paths` 定位内置 node 与脚本。

- [ ] **Step 1: 准备内置运行时**：把 `node.exe` 复制到 `runtime/node/`；在 `runtime/` 下 `npm i silk-wasm`；`decode_silk.js` 放 `runtime/`。写 `runtime/node/VERSION.txt`。
- [ ] **Step 2: 写 `build.spec`**：`Analysis(['app.py'])`，`datas=[('runtime','runtime'),('ui/theme.qss','ui')]`，`EXE`+`COLLECT`，`console=False`。
- [ ] **Step 3: 构建**：`pyinstaller build.spec` → 产物在 `dist/WxVoiceTool/`。
- [ ] **Step 4: 验收**：把 `dist/WxVoiceTool/` 复制到别的目录运行，确认能启动、能取密钥、能导出（验证内置 node 生效）。记录产物大小。
- [ ] **Step 5: 写 `README.md`**：用途、使用步骤、依赖、打包方式、**仅用于导出本人有权处理的数据**的说明。
- [ ] **Step 6: 提交**：`git commit -am "build: package standalone exe"`。

---

## Self-Review

- **Spec coverage**：定位(Task2)/取密钥(Task4，含缓存+手动 key)/解密(Task3)/索引(Task6)/导出(Task7，含时长/格式/目录)/GUI(Task8)/打包(Task9) 均有任务；非目标未纳入。
- **类型一致性**：`VoiceClip`/`ContactVoices` 在 Task6 定义、Task7 使用；`decode_silk` Task5 定义、Task7 注入；`KeyResult` 仅 Task4 内部与缓存。
- **Review Focus**：微信未运行→Task4 Step5 提示；版本变化→Task4 手动 key 路径；库占用→Task6 逐库 try；大库→Task8 QThread+进度；SILK 异常→Task7 逐条 try。
- **比例**：任务为可独立验收的最小单元，未展开函数体。
