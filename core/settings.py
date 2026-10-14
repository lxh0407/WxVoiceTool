import json

from core import paths


def load() -> dict:
    try:
        return json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    paths.ensure_dirs()
    paths.CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
