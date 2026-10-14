import core.voiceexport as E
from core.voiceindex import ContactVoices, VoiceClip


def test_select_clips_accumulates_to_target():
    clips = [VoiceClip(1, 10, 4000), VoiceClip(2, 20, 7000), VoiceClip(3, 30, 9000)]
    sel = E.select_clips(clips, 10000)
    assert [c.server_id for c in sel] == [1, 2]


def test_select_clips_all_if_short():
    clips = [VoiceClip(1, 10, 3000)]
    assert len(E.select_clips(clips, 10000)) == 1


def test_export_contact_writes_wav(tmp_path):
    def fake_decode(b):
        return b"\x01\x02" * 100

    c = ContactVoices("wxid_a", "A", [VoiceClip(1, 1, 1000)], 1000, 1000)
    out = E.export_contact(c, {1: b"silk"}, 1000, "wav", tmp_path, fake_decode)
    assert out.suffix == ".wav" and out.read_bytes()[:4] == b"RIFF"


def test_export_contact_writes_mp3(tmp_path):
    c = ContactVoices("wxid_a", "A", [VoiceClip(1, 1, 1000)], 1000, 1000)
    out = E.export_contact(c, {1: b"silk"}, 1000, "mp3", tmp_path, lambda b: b"\x00\x00" * 1000)
    assert out.suffix == ".mp3" and out.stat().st_size > 0
