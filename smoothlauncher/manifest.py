"""Fetch the Mojang version manifest and per-version JSONs."""
from __future__ import annotations
import json
from typing import Optional

from . import config
from .utils import http_get_json, download

_manifest_cache: Optional[dict] = None


def get_manifest(force: bool = False) -> dict:
    global _manifest_cache
    if _manifest_cache is None or force:
        _manifest_cache = http_get_json(config.VERSION_MANIFEST)
    return _manifest_cache


def list_versions(include_snapshots: bool = False) -> list[dict]:
    """Return version entries (newest first), releases only by default."""
    data = get_manifest()
    out = []
    for v in data.get("versions", []):
        if include_snapshots or v.get("type") == "release":
            out.append(v)
    return out


def latest_release() -> str:
    return get_manifest()["latest"]["release"]


def _entry_for(version_id: str) -> dict:
    for v in get_manifest().get("versions", []):
        if v["id"] == version_id:
            return v
    raise ValueError(f"Unknown Minecraft version: {version_id}")


def get_version_json(version_id: str) -> dict:
    """Fetch (and cache to disk) the vanilla version JSON."""
    dest = config.VERSIONS_DIR / version_id / f"{version_id}.json"
    if dest.exists():
        return json.loads(dest.read_text("utf-8"))
    entry = _entry_for(version_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    download(entry["url"], dest, sha1=entry.get("sha1"))
    return json.loads(dest.read_text("utf-8"))
