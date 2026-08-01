"""Unified mod browser: search Modrinth (open API) and CurseForge (needs key),
and install a mod's newest matching file into an instance's mods folder.

CurseForge marks some files as no-third-party-download (downloadUrl is null).
Those can't be fetched programmatically, so we report `manual` + the website URL
and the UI opens it in a browser instead.
"""
from __future__ import annotations
import json
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import config, settings
from .utils import http_get_json, download

Log = Optional[Callable[[str], None]]

# CurseForge numeric loader types
_CF_LOADER = {"fabric": 4, "forge": 1, "quilt": 5, "neoforge": 6, "vanilla": 0, "": 0}
_CF_GAME_ID = 432
_CF_MOD_CLASS = 6

# Modrinth loader facet strings
_MR_LOADERS = {"fabric", "forge", "quilt", "neoforge"}


@dataclass
class ModResult:
    source: str            # "modrinth" | "curseforge"
    project_id: str
    name: str
    author: str
    description: str
    downloads: int
    website_url: str
    icon_url: str = ""


# --------------------------------------------------------------------------- #
# Modrinth                                                                     #
# --------------------------------------------------------------------------- #
def _cf_headers() -> dict:
    return {"x-api-key": settings.get_cf_key(), "Accept": "application/json"}


def search_modrinth(query: str, mc_version: str, loader: str, limit: int = 20) -> list[ModResult]:
    facets = [["project_type:mod"]]
    if loader in _MR_LOADERS:
        facets.append([f"categories:{loader}"])
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    params = urllib.parse.urlencode({
        "query": query, "limit": limit, "facets": json.dumps(facets),
    })
    data = http_get_json(f"{config.MODRINTH_API}/search?{params}")
    out = []
    for h in data.get("hits", []):
        out.append(ModResult(
            source="modrinth",
            project_id=h.get("project_id") or h.get("slug"),
            name=h.get("title", "?"),
            author=h.get("author", ""),
            description=h.get("description", ""),
            downloads=h.get("downloads", 0),
            website_url=f"https://modrinth.com/mod/{h.get('slug')}",
            icon_url=h.get("icon_url", "") or "",
        ))
    return out


def install_modrinth(result: ModResult, mc_version: str, loader: str,
                     mods_dir: Path, log: Log = None) -> tuple[str, str]:
    loaders = f'["{loader}"]' if loader in _MR_LOADERS else "[]"
    url = (f"{config.MODRINTH_API}/project/{result.project_id}/version"
           f'?game_versions=["{mc_version}"]&loaders={loaders}')
    versions = http_get_json(url)
    if not versions:
        return ("none", f"No build of {result.name} for {loader} {mc_version}")
    files = versions[0].get("files", [])
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not primary:
        return ("none", f"No downloadable file for {result.name}")
    mods_dir.mkdir(parents=True, exist_ok=True)
    download(primary["url"], mods_dir / primary["filename"],
             sha1=primary.get("hashes", {}).get("sha1"), log=log)
    return ("ok", primary["filename"])


# --------------------------------------------------------------------------- #
# CurseForge                                                                   #
# --------------------------------------------------------------------------- #
def search_curseforge(query: str, mc_version: str, loader: str, limit: int = 20) -> list[ModResult]:
    if not settings.get_cf_key():
        raise RuntimeError("No CurseForge API key set.")
    params = {
        "gameId": _CF_GAME_ID, "classId": _CF_MOD_CLASS, "searchFilter": query,
        "pageSize": limit, "sortField": 2, "sortOrder": "desc",
    }
    if mc_version:
        params["gameVersion"] = mc_version
    if loader in _CF_LOADER and _CF_LOADER[loader]:
        params["modLoaderType"] = _CF_LOADER[loader]
    url = f"https://api.curseforge.com/v1/mods/search?{urllib.parse.urlencode(params)}"
    data = http_get_json(url, headers=_cf_headers())
    out = []
    for m in data.get("data", []):
        authors = m.get("authors", [])
        out.append(ModResult(
            source="curseforge",
            project_id=str(m.get("id")),
            name=m.get("name", "?"),
            author=authors[0].get("name", "") if authors else "",
            description=m.get("summary", ""),
            downloads=int(m.get("downloadCount", 0)),
            website_url=m.get("links", {}).get("websiteUrl", ""),
            icon_url=(m.get("logo") or {}).get("thumbnailUrl", "") or "",
        ))
    return out


def install_curseforge(result: ModResult, mc_version: str, loader: str,
                       mods_dir: Path, log: Log = None) -> tuple[str, str]:
    params = {}
    if mc_version:
        params["gameVersion"] = mc_version
    if loader in _CF_LOADER and _CF_LOADER[loader]:
        params["modLoaderType"] = _CF_LOADER[loader]
    url = (f"https://api.curseforge.com/v1/mods/{result.project_id}/files"
           f"?{urllib.parse.urlencode(params)}")
    data = http_get_json(url, headers=_cf_headers()).get("data", [])
    if not data:
        return ("none", f"No build of {result.name} for {loader} {mc_version}")
    f = data[0]
    dl = f.get("downloadUrl")
    if not dl:
        # Author disabled third-party downloads -> must grab it from the site.
        return ("manual", result.website_url or "https://www.curseforge.com")
    sha1 = next((h["value"] for h in f.get("hashes", []) if h.get("algo") == 1), None)
    mods_dir.mkdir(parents=True, exist_ok=True)
    download(dl, mods_dir / f["fileName"], sha1=sha1, log=log)
    return ("ok", f["fileName"])


# --------------------------------------------------------------------------- #
# Dispatch                                                                     #
# --------------------------------------------------------------------------- #
def search(source: str, query: str, mc_version: str, loader: str) -> list[ModResult]:
    if source == "curseforge":
        return search_curseforge(query, mc_version, loader)
    return search_modrinth(query, mc_version, loader)


def install(result: ModResult, mc_version: str, loader: str,
            mods_dir: Path, log: Log = None) -> tuple[str, str]:
    if result.source == "curseforge":
        return install_curseforge(result, mc_version, loader, mods_dir, log=log)
    return install_modrinth(result, mc_version, loader, mods_dir, log=log)
