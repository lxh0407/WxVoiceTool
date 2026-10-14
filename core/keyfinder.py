import ctypes
import hmac
import json
import re
import struct
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

import yara
from Crypto.Hash import SHA512
from Crypto.Protocol.KDF import PBKDF2

from core import paths
from core.dbdecrypt import IV_SZ, PAGE, RESERVE, make_enc_key

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_GUARD = 0x100
TH32CS_SNAPPROCESS = 0x2

_RULE = r"""
rule GetKeyAddrStub {
    strings:
        $a = { ?? ?? ?? ?? ?? ?? 00 00 00 00 00 00 00 00 00 00 20 00 00 00 00 00 00 00 2f 00 00 00 00 00 00 00 }
    condition:
        all of them
}
"""
_rules = yara.compile(source=_RULE)

_STATIC = re.compile(
    b"\x48\xBA(.{8}).{3,8}?\x48\xBA(.{8}).{3,8}?\x48\xBA(.{8}).{3,8}?\x48\xBA(.{8}).{3,8}?\x48\x85\xC0",
    re.DOTALL,
)


@dataclass
class KeyResult:
    passphrase_hex: str
    account: str
    version: str
    source: str


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def xor_raw(raw: bytes, xor_key: bytes) -> bytes:
    if len(raw) != len(xor_key):
        raise ValueError("raw and xor_key must be same length")
    return bytes(a ^ b for a, b in zip(raw, xor_key))


def parse_manual_key(text: str, account: str) -> KeyResult:
    key = re.sub(r"\s+", "", text or "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", key):
        raise ValueError("密钥必须是 64 位十六进制 (32 字节)")
    return KeyResult(key.lower(), account, "", "manual")


def validate(raw: bytes, xor_key: bytes, db_path) -> bytes | None:
    try:
        page = Path(db_path).read_bytes()[:PAGE]
    except OSError:
        return None
    if len(page) < PAGE:
        return None
    salt = page[:16]
    mac_salt = bytes(b ^ 0x3A for b in salt)
    pp = xor_raw(raw, xor_key)
    enc = make_enc_key(pp, salt)
    mac_key = PBKDF2(enc, mac_salt, dkLen=32, count=2, hmac_hash_module=SHA512)
    mac = hmac.new(mac_key, page[16:PAGE - RESERVE + IV_SZ], SHA512)
    mac.update(struct.pack("<I", 1))
    if mac.digest() == page[PAGE - RESERVE + IV_SZ:PAGE]:
        return pp
    return None


def static_xor_keys(dll) -> list[bytes]:
    data = Path(dll).read_bytes()
    keys: list[bytes] = []
    seen: set[bytes] = set()
    for m in _STATIC.finditer(data):
        key = b"".join(m.group(i) for i in range(1, 5))
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def find_pids(name: str = "Weixin.exe") -> list[int]:
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return []
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(entry)
    pids: list[int] = []
    try:
        ok = k.Process32First(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.decode(errors="ignore").lower() == name.lower():
                pids.append(entry.th32ProcessID)
            ok = k.Process32Next(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return pids


def is_potential_key(key: bytes) -> bool:
    if len(key) != 32:
        return False
    if len(set(key)) < 15:
        return False
    if sum(32 <= b <= 126 for b in key) > 24:
        return False
    return True


def _read_mem(handle, k, address: int, size: int) -> bytes:
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t(0)
    if k.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read)) and read.value:
        return buf.raw[:read.value]
    return b""


def raw_candidates(pid: int) -> list[bytes]:
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return []
    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    regions: list[tuple[int, int]] = []
    while k.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base = ctypes.cast(mbi.BaseAddress, ctypes.c_void_p).value or 0
        size = mbi.RegionSize
        if mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE and not (mbi.Protect & PAGE_GUARD):
            regions.append((base, size))
        if size == 0:
            break
        addr = base + size
    cands: list[bytes] = []
    seen: set[bytes] = set()
    chunk = 4 * 1024 * 1024
    overlap = 64
    try:
        for base, size in regions:
            off = 0
            while off < size:
                n = min(chunk, size - off)
                data = _read_mem(h, k, base + off, n)
                if data:
                    for m in _rules.match(data=data):
                        for s in m.strings:
                            for inst in s.instances:
                                o = inst.offset
                                if o + 8 > len(data):
                                    continue
                                ptr = struct.unpack_from("<Q", data, 0 + o)[0]
                                raw = _read_mem(h, k, ptr, 32)
                                if raw and raw not in seen and is_potential_key(raw):
                                    seen.add(raw)
                                    cands.append(raw)
                if n >= size - off:
                    break
                off += n - overlap
    finally:
        k.CloseHandle(h)
    return cands


def recover_key(account, dll, db_path, progress=None) -> KeyResult | None:
    pids = find_pids("Weixin.exe")
    if not pids:
        raise RuntimeError("未检测到运行中的微信（Weixin.exe），请先登录并保持微信运行")
    xors = static_xor_keys(dll)
    if not xors:
        raise RuntimeError("未能从 Weixin.dll 提取密钥特征（微信版本可能已变化）")
    version = Path(dll).parent.name
    raws: list[bytes] = []
    for i, pid in enumerate(pids):
        if progress:
            progress(i, len(pids))
        raws += raw_candidates(pid)
    uniq = list(dict.fromkeys(raws))
    for xor in xors:
        for raw in uniq:
            pp = validate(raw, xor, db_path)
            if pp:
                return KeyResult(pp.hex(), account.wxid, version, "memory")
    return None


def load_cache() -> dict | None:
    try:
        return json.loads(paths.CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_cache(result: KeyResult) -> None:
    paths.ensure_dirs()
    paths.CACHE_FILE.write_text(
        json.dumps({"passphrase_hex": result.passphrase_hex, "account": result.account,
                    "version": result.version, "source": result.source}, ensure_ascii=False),
        encoding="utf-8",
    )
