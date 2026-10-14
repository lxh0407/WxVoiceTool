import struct

import core.silk as S


def test_pcm_to_wav_header():
    wav = S.pcm_to_wav(b"\x00\x00" * 100, 24000)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert struct.unpack("<I", wav[24:28])[0] == 24000
    assert struct.unpack("<H", wav[22:24])[0] == 1
    assert struct.unpack("<H", wav[34:36])[0] == 16
    assert struct.unpack("<I", wav[40:44])[0] == 200
