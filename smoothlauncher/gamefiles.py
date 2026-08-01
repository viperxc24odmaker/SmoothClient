"""Download client jar, libraries (+ natives), and assets for a version JSON."""
from __future__ import annotations
import json
import zipfile
from pathlib import Path
from typing import Callable, Optional

from . import config
from .utils import (download, http_get_json, maven_to_path, os_name,
                    rules_allow)

Log = Optional[Callable[[str], None]]


# --------------------------------------------------------------------------- #
# Client jar                                                                   #
# --------------------------------------------------------------------------- #
def client_jar_path(version_id: str) -> Path:
    return config.VERSIONS_DIR / version_id / f"{version_id}.jar"


def download_client_jar(vjson: dict, log: Log = None) -> Path:
    vid = vjson["id"]
    dest = client_jar_path(vid)
    client = vjson.get("downloads", {}).get("client")
    if client:
        download(client["url"], dest, sha1=client.get("sha1"), log=log)
    return dest


# --------------------------------------------------------------------------- #
# Libraries + natives                                                          #
# --------------------------------------------------------------------------- #
def _native_classifier(lib: dict) -> Optional[str]:
    """Old-style natives: `natives` maps os -> classifier key."""
    natives = lib.get("natives")
    if not natives:
        return None
    key = natives.get(os_name())
    if key:
        return key.replace("${arch}", "64")
    return None


def collect_libraries(vjson: dict, log: Log = None):
    """Download all applicable libraries.

    Returns (classpath_jars, native_jars_to_extract).
    """
    classpath: list[Path] = []
    natives: list[Path] = []
    for lib in vjson.get("libraries", []):
        if not rules_allow(lib.get("rules")):
            continue
        downloads = lib.get("downloads", {})

        # regular artifact -> classpath
        artifact = downloads.get("artifact")
        if artifact and artifact.get("path"):
            dest = config.LIBRARIES_DIR / artifact["path"]
            if artifact.get("url"):
                download(artifact["url"], dest, sha1=artifact.get("sha1"), log=log)
            classpath.append(dest)
        elif "name" in lib and not lib.get("natives"):
            # Fabric/Forge style: name + maven base url, no downloads block
            rel = maven_to_path(lib["name"])
            dest = config.LIBRARIES_DIR / rel
            base = lib.get("url") or config.FORGE_MAVEN + "/"
            if not base.endswith("/"):
                base += "/"
            try:
                download(base + rel, dest, sha1=None, log=log)
                classpath.append(dest)
            except Exception as e:  # some Forge libs are produced by processors, not fetched
                if log:
                    log(f"  (skip fetch, expected local) {dest.name}: {e}")
                if dest.exists():
                    classpath.append(dest)

        # old-style native classifier -> extract later
        classifier = _native_classifier(lib)
        if classifier:
            cls = downloads.get("classifiers", {}).get(classifier)
            if cls and cls.get("path"):
                dest = config.LIBRARIES_DIR / cls["path"]
                download(cls["url"], dest, sha1=cls.get("sha1"), log=log)
                natives.append(dest)
    return classpath, natives


def extract_natives(native_jars: list[Path], target: Path, log: Log = None) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    for jar in native_jars:
        try:
            with zipfile.ZipFile(jar) as z:
                for member in z.namelist():
                    if member.startswith("META-INF/") or member.endswith("/"):
                        continue
                    if member.endswith((".dll", ".so", ".dylib", ".jnilib")):
                        z.extract(member, target)
        except zipfile.BadZipFile:
            if log:
                log(f"  bad native jar: {jar.name}")
    # flatten any nested dirs so java.library.path finds the binaries
    for p in list(target.rglob("*")):
        if p.is_file() and p.parent != target:
            dest = target / p.name
            if not dest.exists():
                p.replace(dest)
    return target


# --------------------------------------------------------------------------- #
# Assets                                                                       #
# --------------------------------------------------------------------------- #
def download_assets(vjson: dict, log: Log = None) -> str:
    ai = vjson.get("assetIndex")
    if not ai:
        return vjson.get("assets", "legacy")
    index_id = ai["id"]
    index_path = config.ASSETS_DIR / "indexes" / f"{index_id}.json"
    download(ai["url"], index_path, sha1=ai.get("sha1"), log=log)
    index = json.loads(index_path.read_text("utf-8"))

    objects = index.get("objects", {})
    total = len(objects)
    if log:
        log(f"  {total} asset objects")
    for i, (name, obj) in enumerate(objects.items()):
        h = obj["hash"]
        sub = h[:2]
        dest = config.ASSETS_DIR / "objects" / sub / h
        url = f"{config.RESOURCES_BASE}/{sub}/{h}"
        download(url, dest, sha1=h)
        if log and total and (i + 1) % 200 == 0:
            log(f"  assets {i + 1}/{total}")

    # legacy / virtual layouts
    if index.get("virtual") or index.get("map_to_resources"):
        base = config.ASSETS_DIR / ("virtual" if index.get("virtual") else "resources")
        if index.get("virtual"):
            base = base / index_id
        for name, obj in objects.items():
            src = config.ASSETS_DIR / "objects" / obj["hash"][:2] / obj["hash"]
            dst = base / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                dst.write_bytes(src.read_bytes())
    return index_id
