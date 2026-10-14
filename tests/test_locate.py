from pathlib import Path

import core.locate as L


def test_wxid_from_dirname_strips_suffix():
    assert L.wxid_from_dirname("wxid_jng2lqldeiag21_23b7") == "wxid_jng2lqldeiag21"
    assert L.wxid_from_dirname("zitang90") == "zitang90"


def test_find_data_root_reads_ini(tmp_path):
    cfg = tmp_path / "Tencent" / "xwechat" / "config"
    cfg.mkdir(parents=True)
    (cfg / "a.ini").write_text("E:\\WX\\Documents\n", encoding="utf-8")
    assert L.find_data_root(appdata=tmp_path) == Path("E:\\WX\\Documents") / "xwechat_files"


def test_find_accounts_lists_dirs(tmp_path):
    (tmp_path / "all_users").mkdir()
    acc = tmp_path / "wxid_a_1234"
    (acc / "db_storage").mkdir(parents=True)
    accts = L.find_accounts(tmp_path)
    assert [a.wxid for a in accts] == ["wxid_a"]
