"""Per-instance performance pack. Fabric-only. Pulls the correct build for the
instance's MC version straight from Modrinth's open API (no key needed)."""
from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional

from . import config
from .utils import http_get_json, download

Log = Optional[Callable[[str], None]]

# Modrinth project slugs
PACKS = {
    "vulkanmod": ["vulkanmod"],
    "sodium": ["sodium", "lithium"],
    "none": [],
}


def _best_file(slug: str, mc_version: str) -> Optional[tuple[str, str, str]]:
    """Return (url, filename, sha1) of the newest Fabric build for mc_version."""
    url = (f"{config.MODRINTH_API}/project/{slug}/version"
           f'?loaders=["fabric"]&game_versions=["{mc_version}"]')
    try:
        versions = http_get_json(url)
    except Exception:
        return None
    if not versions:
        return None
    files = versions[0].get("files", [])
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not primary:
        return None
    return primary["url"], primary["filename"], primary.get("hashes", {}).get("sha1")


def install_pack(pack: str, mc_version: str, mods_dir: Path, log: Log = None) -> list[str]:
    """Download the chosen performance mods into mods_dir. Returns installed names."""
    pack = (pack or "none").lower()
    slugs = PACKS.get(pack, [])
    mods_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for slug in slugs:
        info = _best_file(slug, mc_version)
        if not info:
            if log:
                log(f"  no {slug} build for MC {mc_version} (skipped)")
            continue
        url, filename, sha1 = info
        download(url, mods_dir / filename, sha1=sha1, log=log)
        installed.append(filename)
        if log:
            log(f"  + {filename}")
    return installed
