"""Tiny settings store (currently just the CurseForge API key)."""
from __future__ import annotations
import json
import os

from . import config


def load_settings() -> dict:
    if config.SETTINGS_FILE.exists():
        try:
            return json.loads(config.SETTINGS_FILE.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_settings(data: dict) -> None:
    config.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SETTINGS_FILE.write_text(json.dumps(data, indent=2), "utf-8")


def get_cf_key() -> str:
    return os.environ.get("SMOOTH_CF_API_KEY") or load_settings().get("cf_api_key", "")


def set_cf_key(key: str) -> None:
    data = load_settings()
    data["cf_api_key"] = key.strip()
    save_settings(data)
