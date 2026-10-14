import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
USER_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WxVoiceTool"
WORK_DIR = USER_DIR / "work"
CACHE_FILE = USER_DIR / "key.json"
LOG_DIR = USER_DIR / "logs"
DEFAULT_OUT_DIR = Path.home() / "WxVoiceSamples"


def ensure_dirs() -> None:
    for d in (USER_DIR, WORK_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
