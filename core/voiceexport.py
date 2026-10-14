from pathlib import Path

import lameenc

from core.silk import SAMPLE_RATE, pcm_to_wav


def select_clips(clips, target_ms: int) -> list:
    out = []
    acc = 0
    for c in sorted(clips, key=lambda c: c.create_time):
        if acc >= target_ms:
            break
        out.append(c)
        acc += c.length_ms
    return out


def encode_mp3(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    enc = lameenc.Encoder()
    enc.set_bit_rate(64)
    enc.set_in_sample_rate(sample_rate)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode(bytes(pcm))
    data += enc.flush()
    return bytes(data)


def _safe(name: str) -> str:
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()[:40] or "unknown"


def export_contact(contact, voice_map: dict, target_ms: int, fmt: str,
                   out_dir, decode) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = select_clips(contact.clips, target_ms)
    pcm = bytearray()
    for c in clips:
        data = voice_map.get(c.server_id)
        if not data:
            continue
        try:
            pcm += decode(data)
        except Exception:
            continue
    if fmt == "mp3":
        path = out_dir / ("%s_%s.mp3" % (_safe(contact.name), contact.username))
        path.write_bytes(encode_mp3(bytes(pcm)))
    else:
        path = out_dir / ("%s_%s.wav" % (_safe(contact.name), contact.username))
        path.write_bytes(pcm_to_wav(bytes(pcm)))
    return path
