"""Resolve a Java executable: prefer the Mojang-provided runtime for the
version's required component, fall back to a system Java on PATH/JAVA_HOME."""
from __future__ import annotations
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Callable, Optional

from . import config
from .utils import download, http_get_json, java_runtime_platform

Log = Optional[Callable[[str], None]]


def _java_binary(runtime_root: Path) -> Path:
    if sys.platform == "win32":
        return runtime_root / "bin" / "java.exe"
    if sys.platform == "darwin":
        return runtime_root / "jre.bundle" / "Contents" / "Home" / "bin" / "java"
    return runtime_root / "bin" / "java"


def download_runtime(vjson: dict, log: Log = None) -> Optional[Path]:
    """Download the Mojang JRE named by vjson['javaVersion']['component']."""
    comp = vjson.get("javaVersion", {}).get("component", "jre-legacy")
    plat = java_runtime_platform()
    runtime_root = config.RUNTIMES_DIR / comp / plat
    java_bin = _java_binary(runtime_root)
    if java_bin.exists():
        return java_bin

    if log:
        log(f"Fetching Java runtime '{comp}' for {plat} ...")
    allj = http_get_json(config.JAVA_RUNTIME_MANIFEST)
    entries = allj.get(plat, {}).get(comp, [])
    if not entries:
        if log:
            log(f"No Mojang runtime for {comp}/{plat}; will try system Java.")
        return None
    files_manifest = http_get_json(entries[0]["manifest"]["url"])

    for rel, meta in files_manifest.get("files", {}).items():
        target = runtime_root / rel
        kind = meta.get("type")
        if kind == "directory":
            target.mkdir(parents=True, exist_ok=True)
        elif kind == "file":
            raw = meta.get("downloads", {}).get("raw", {})
            if raw.get("url"):
                download(raw["url"], target, sha1=raw.get("sha1"))
                if meta.get("executable"):
                    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        elif kind == "link":
            tgt = meta.get("target")
            if tgt and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.symlink(tgt, target)
                except OSError:
                    pass
    if java_bin.exists():
        return java_bin
    if log:
        log("Runtime download finished but java binary not found.")
    return None


def system_java() -> Optional[Path]:
    jh = os.environ.get("JAVA_HOME")
    if jh:
        cand = Path(jh) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
        if cand.exists():
            return cand
    found = shutil.which("java")
    return Path(found) if found else None


def resolve_java(vjson: dict, override: Optional[str] = None, log: Log = None) -> Path:
    if override:
        p = Path(override)
        if p.exists():
            return p
        if log:
            log(f"Custom Java path not found: {override}")
    try:
        rt = download_runtime(vjson, log=log)
        if rt:
            return rt
    except Exception as e:
        if log:
            log(f"Runtime download failed ({e}); trying system Java.")
    sysj = system_java()
    if sysj:
        return sysj
    raise RuntimeError(
        "No Java runtime available. Install Java or set a custom Java path in Settings."
    )
