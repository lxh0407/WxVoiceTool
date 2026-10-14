import struct
import subprocess
import tempfile
from pathlib import Path

from core import paths

SAMPLE_RATE = 24000


def _node_path() -> str:
    bundled = paths.APP_DIR / "runtime" / "node" / "node.exe"
    return str(bundled) if bundled.exists() else "node"


def _script_path() -> Path:
    return paths.APP_DIR / "runtime" / "decode_silk.js"


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    ch, bits = 1, 16
    header = bytearray(44)
    header[0:4] = b"RIFF"
    struct.pack_into("<I", header, 4, 36 + len(pcm))
    header[8:12] = b"WAVE"
    header[12:16] = b"fmt "
    struct.pack_into("<I", header, 16, 16)
    struct.pack_into("<H", header, 20, 1)
    struct.pack_into("<H", header, 22, ch)
    struct.pack_into("<I", header, 24, sample_rate)
    struct.pack_into("<I", header, 28, sample_rate * ch * bits // 8)
    struct.pack_into("<H", header, 32, ch * bits // 8)
    struct.pack_into("<H", header, 34, bits)
    header[36:40] = b"data"
    struct.pack_into("<I", header, 40, len(pcm))
    return bytes(header) + pcm


def decode_silk(silk_bytes: bytes, sample_rate: int = SAMPLE_RATE,
                node_exe: str | None = None, script: Path | None = None) -> bytes:
    node_exe = node_exe or _node_path()
    script = script or _script_path()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "clip.silk"
        src.write_bytes(bytes(silk_bytes))
        out = Path(str(src) + ".pcm")
        proc = subprocess.run([node_exe, str(script), str(src), str(sample_rate)],
                              capture_output=True)
        if not out.exists():
            raise RuntimeError("SILK 解码失败: " + proc.stderr.decode("utf-8", "ignore")[:300])
        return out.read_bytes()
