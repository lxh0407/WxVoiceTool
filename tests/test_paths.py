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
