"""Low-level helpers: platform detection, Mojang rule evaluation, maven path
resolution, hashed downloads, and version-JSON inheritance merging."""
from __future__ import annotations
import hashlib
import platform
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Callable, Optional

from . import config


# --------------------------------------------------------------------------- #
# Platform detection (matches the strings Mojang uses in its rules)            #
# --------------------------------------------------------------------------- #
def os_name() -> str:
    p = platform.system()
    return {"Windows": "windows", "Darwin": "osx", "Linux": "linux"}.get(p, "linux")


def os_arch() -> str:
    m = platform.machine().lower()
    if m in ("amd64", "x86_64", "x64"):
        return "x64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("i386", "i686", "x86"):
        return "x86"
    return "x64"


def java_runtime_platform() -> str:
    """Key used in Mojang's java-runtime all.json manifest."""
    o, a = os_name(), os_arch()
    if o == "windows":
        return {"x64": "windows-x64", "x86": "windows-x86", "arm64": "windows-arm64"}.get(a, "windows-x64")
    if o == "osx":
        return "mac-os-arm64" if a == "arm64" else "mac-os"
    return "linux" if a == "x64" else "linux-i386"


# --------------------------------------------------------------------------- #
# Rule evaluation (libraries + arguments)                                      #
# --------------------------------------------------------------------------- #
def rules_allow(rules: Optional[list], features: Optional[dict] = None) -> bool:
    """Evaluate a Mojang `rules` array. Empty/absent -> allowed."""
    if not rules:
        return True
    features = features or {}
    allowed = False
    for rule in rules:
        applies = True
        os_cond = rule.get("os")
        if os_cond:
            if "name" in os_cond and os_cond["name"] != os_name():
                applies = False
            if "arch" in os_cond and os_cond["arch"] != os_arch():
                applies = False
            # `version` regex conditions are ignored (rarely used, safe default)
        feat_cond = rule.get("features")
        if feat_cond:
            for key, want in feat_cond.items():
                if bool(features.get(key, False)) != bool(want):
                    applies = False
        if applies:
            allowed = rule.get("action") == "allow"
    return allowed


# --------------------------------------------------------------------------- #
# Maven coordinates -> relative path                                           #
# --------------------------------------------------------------------------- #
def maven_to_path(name: str) -> str:
    """`group:artifact:version[:classifier][@ext]` -> maven-style relative path."""
    ext = "jar"
    coord = name
    if "@" in coord:
        coord, ext = coord.split("@", 1)
    parts = coord.split(":")
    group, artifact, version = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else None
    fname = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + f".{ext}"
    return "/".join(group.split(".")) + f"/{artifact}/{version}/{fname}"


def artifact_key(name: str) -> str:
    """`group:artifact` identity used to dedupe libraries across parent/child."""
    parts = name.split(":")
    return f"{parts[0]}:{parts[1]}"


# --------------------------------------------------------------------------- #
# Networking                                                                   #
# --------------------------------------------------------------------------- #
def _request(url: str, data: bytes = None, headers: dict = None, method: str = None):
    hdrs = {"User-Agent": config.USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    return urllib.request.urlopen(req, timeout=60)


def http_get_json(url: str, headers: dict = None) -> Any:
    import json
    with _request(url, headers=headers) as r:
        return json.loads(r.read().decode("utf-8"))


def http_post_json(url: str, payload: dict = None, form: dict = None, headers: dict = None) -> Any:
    import json
    import urllib.parse
    hdrs = dict(headers or {})
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    else:
        body = json.dumps(payload or {}).encode()
        hdrs.setdefault("Content-Type", "application/json")
    hdrs.setdefault("Accept", "application/json")
    with _request(url, data=body, headers=hdrs, method="POST") as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, sha1: Optional[str] = None,
             log: Optional[Callable[[str], None]] = None) -> Path:
    """Download `url` -> `dest`, skipping if a valid (sha1-matched) copy exists."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        if sha1 is None or sha1_of(dest) == sha1:
            return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with _request(url) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Download failed ({e.code}) for {url}") from e
    if sha1 is not None and sha1_of(tmp) != sha1:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"SHA1 mismatch for {url}")
    tmp.replace(dest)
    if log:
        log(f"  downloaded {dest.name}")
    return dest


# --------------------------------------------------------------------------- #
# Version-JSON inheritance (Fabric / Forge use `inheritsFrom`)                 #
# --------------------------------------------------------------------------- #
def merge_versions(parent: dict, child: dict) -> dict:
    """Merge a loader profile (`child`) onto its base vanilla JSON (`parent`)."""
    merged = dict(parent)

    for key in ("id", "mainClass", "assets", "type", "releaseTime", "time",
                "minecraftArguments", "javaVersion"):
        if child.get(key) is not None:
            merged[key] = child[key]
    if child.get("assetIndex"):
        merged["assetIndex"] = child["assetIndex"]

    # libraries: loader libs win on conflict, keep first occurrence
    seen: set[str] = set()
    libs: list[dict] = []
    for lib in child.get("libraries", []) + parent.get("libraries", []):
        key = artifact_key(lib.get("name", ""))
        if key in seen:
            continue
        seen.add(key)
        libs.append(lib)
    merged["libraries"] = libs

    # modern argument arrays get concatenated (parent first, loader appends)
    if "arguments" in parent or "arguments" in child:
        pa = parent.get("arguments", {})
        ca = child.get("arguments", {})
        merged["arguments"] = {
            "game": list(pa.get("game", [])) + list(ca.get("game", [])),
            "jvm": list(pa.get("jvm", [])) + list(ca.get("jvm", [])),
        }
    return merged
