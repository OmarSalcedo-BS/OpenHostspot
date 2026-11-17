"""Información compartida por la aplicación y el empaquetador."""

import json
from pathlib import Path


INFO_PATH = Path(__file__).with_name("app_info.json")


def load_app_info(path: Path = INFO_PATH) -> dict[str, str]:
    with path.open(encoding="utf-8") as file:
        info = json.load(file)
    if not isinstance(info, dict) or any(
        not isinstance(info.get(key), str) or not info[key].strip()
        for key in ("name", "version", "description", "author", "license", "copyright")
    ):
        raise ValueError(f"Información de aplicación no válida: {path}")
    return info


APP_INFO = load_app_info()
