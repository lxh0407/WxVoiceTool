import core.settings as S


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(S.paths, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(S.paths, "USER_DIR", tmp_path)
    S.save({"data_root": "E:\\WX\\Documents\\xwechat_files", "dll": "C:\\x\\Weixin.dll", "account_dir": ""})
    assert S.load()["data_root"].endswith("xwechat_files")


def test_settings_load_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(S.paths, "CONFIG_FILE", tmp_path / "nope.json")
    assert S.load() == {}
