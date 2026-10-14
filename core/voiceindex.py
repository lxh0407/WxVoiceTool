import re
import sqlite3
from dataclasses import dataclass

import zstandard as zstd

_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_VOICE_LEN = re.compile(rb'voicelength="(\d+)"')
_dctx = zstd.ZstdDecompressor()


@dataclass
class VoiceClip:
    server_id: int
    create_time: int
    length_ms: int


@dataclass
class ContactVoices:
    username: str
    name: str
    clips: list
    total_ms: int
    extractable_ms: int


def extract_voicelength(content) -> int | None:
    if not isinstance(content, (bytes, bytearray)):
        return None
    data = bytes(content)
    if data[:4] == _ZSTD_MAGIC:
        try:
            data = _dctx.decompress(data, max_output_size=1 << 22)
        except Exception:
            return None
    m = _VOICE_LEN.search(data)
    return int(m.group(1)) if m else None


def _load_names(con) -> dict:
    cols = [d[1] for d in con.execute("PRAGMA table_info(contact)")]

    def pick(*names):
        for n in names:
            if n in cols:
                return n
        return None

    rem, nick, alias = pick("remark"), pick("nick_name"), pick("alias")
    q = "SELECT username, %s, %s, %s FROM contact" % (
        rem or "NULL", nick or "NULL", alias or "NULL")
    names = {}
    for u, r_, n_, a_ in con.execute(q):
        names[u] = r_ or n_ or a_ or u
    return names


def build_index(message_db, media_db, contact_db, my_wxid: str) -> list:
    msg = sqlite3.connect(str(message_db))
    med = sqlite3.connect(str(media_db))
    con = sqlite3.connect(str(contact_db))
    try:
        names = _load_names(con)
        n2id = {}
        for i, (u,) in enumerate(msg.execute("SELECT user_name FROM Name2Id ORDER BY rowid"), start=1):
            n2id[i] = u
        have = {svr for (svr,) in med.execute("SELECT svr_id FROM VoiceInfo")}
        tables = [r[0] for r in msg.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]
        agg: dict = {}
        for t in tables:
            try:
                cur = msg.execute(
                    "SELECT real_sender_id, server_id, create_time, message_content FROM %s WHERE local_type=34" % t)
            except sqlite3.Error:
                continue
            for rid, sid, ct, content in cur:
                sender = n2id.get(rid)
                if sender is None or sender == my_wxid:
                    continue
                ln = extract_voicelength(content)
                if ln is None:
                    continue
                rec = agg.setdefault(sender, {"total": 0, "ext": 0, "clips": []})
                rec["total"] += ln
                if sid in have:
                    rec["ext"] += ln
                    rec["clips"].append(VoiceClip(sid, ct, ln))
        result = []
        for u, r in agg.items():
            if not r["clips"]:
                continue
            r["clips"].sort(key=lambda c: c.create_time)
            result.append(ContactVoices(u, names.get(u, u), r["clips"], r["total"], r["ext"]))
        result.sort(key=lambda c: -c.extractable_ms)
        return result
    finally:
        msg.close()
        med.close()
        con.close()
