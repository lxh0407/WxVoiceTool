import sqlite3

import zstandard as zstd

import core.voiceindex as V


def _z(b):
    return zstd.ZstdCompressor().compress(b)


def test_extract_voicelength():
    xml = b'wxid_a:\n<msg><voicemsg voicelength="6480" length="12627" voiceformat="4"/></msg>'
    assert V.extract_voicelength(_z(xml)) == 6480
    assert V.extract_voicelength(b"no voice here") is None


def test_build_index_filters_self_and_missing(tmp_path):
    msg = sqlite3.connect(tmp_path / "m.db")
    msg.execute("CREATE TABLE Name2Id(user_name TEXT PRIMARY KEY, is_session INTEGER)")
    msg.execute("INSERT INTO Name2Id VALUES('wxid_a',0)")
    msg.execute("INSERT INTO Name2Id VALUES('wxid_me',0)")
    msg.execute("CREATE TABLE Msg_x(local_id INTEGER, server_id INTEGER, local_type INTEGER, "
                "real_sender_id INTEGER, create_time INTEGER, message_content TEXT)")
    xml = b'<msg><voicemsg voicelength="12000" length="10" voiceformat="4"/></msg>'
    msg.execute("INSERT INTO Msg_x VALUES(1,100,34,1,1,?)", (_z(xml),))
    msg.execute("INSERT INTO Msg_x VALUES(2,101,34,2,2,?)", (_z(xml),))
    msg.execute("INSERT INTO Msg_x VALUES(3,102,34,1,3,?)", (_z(xml),))
    msg.commit()

    med = sqlite3.connect(tmp_path / "v.db")
    med.execute("CREATE TABLE VoiceInfo(chat_name_id INTEGER, create_time INTEGER, local_id INTEGER, "
                "svr_id INTEGER, voice_data BLOB, data_index TEXT)")
    med.execute("INSERT INTO VoiceInfo VALUES(1,1,1,100,?,'0')", (b"\x02#!SILK_V3" + b"0" * 20,))
    med.commit()

    con = sqlite3.connect(tmp_path / "c.db")
    con.execute("CREATE TABLE contact(id INTEGER, username TEXT, local_type INTEGER, alias TEXT, "
                "nick_name TEXT, remark TEXT)")
    con.execute("INSERT INTO contact VALUES(1,'wxid_a',1,'','小A','阿A')")
    con.commit()

    res = V.build_index(tmp_path / "m.db", tmp_path / "v.db", tmp_path / "c.db", "wxid_me")
    assert len(res) == 1
    c = res[0]
    assert c.username == "wxid_a" and c.name == "阿A"
    assert c.total_ms == 24000 and c.extractable_ms == 12000
    assert [x.server_id for x in c.clips] == [100]
