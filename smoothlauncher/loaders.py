"""Mod-loader support.

Fabric  -> uses meta.fabricmc.net which returns a ready-to-merge profile JSON.
Forge   -> runs Forge's own installer headlessly (SimpleInstaller --install-client),
           then reads the version JSON it writes. Forge can't be merged by hand
           because it runs binary-patch processors that need a JVM.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Callable, Optional

from . import config
from .utils import http_get_json, download

Log = Optional[Callable[[str], None]]


# --------------------------------------------------------------------------- #
# Fabric                                                                       #
# --------------------------------------------------------------------------- #
def fabric_loader_versions(mc_version: str) -> list[str]:
    url = f"{config.FABRIC_META}/versions/loader/{mc_version}"
    data = http_get_json(url)
    return [e["loader"]["version"] for e in data]


def latest_fabric_loader(mc_version: str) -> str:
    url = f"{config.FABRIC_META}/versions/loader/{mc_version}"
    data = http_get_json(url)
    for e in data:
        if e["loader"].get("stable"):
            return e["loader"]["version"]
    if not data:
        raise RuntimeError(f"No Fabric loader for Minecraft {mc_version}")
    return data[0]["loader"]["version"]


def fabric_profile(mc_version: str, loader_version: Optional[str] = None,
                   log: Log = None) -> dict:
    """Return the Fabric profile JSON (a version JSON with inheritsFrom)."""
    loader_version = loader_version or latest_fabric_loader(mc_version)
    if log:
        log(f"Fabric loader {loader_version} for MC {mc_version}")
    url = f"{config.FABRIC_META}/versions/loader/{mc_version}/{loader_version}/profile/json"
    profile = http_get_json(url)
    vid = profile.get("id", f"fabric-loader-{loader_version}-{mc_version}")
    dest = config.VERSIONS_DIR / vid / f"{vid}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(profile, indent=2), "utf-8")
    return profile


# --------------------------------------------------------------------------- #
# Forge                                                                        #
# --------------------------------------------------------------------------- #
def resolve_forge_version(mc_version: str, channel: str = "recommended") -> str:
    """Resolve a Forge build for an MC version via the promotions feed."""
    promos = http_get_json(config.FORGE_PROMOTIONS).get("promos", {})
    key = f"{mc_version}-{channel}"
    if key in promos:
        return promos[key]
    if f"{mc_version}-latest" in promos:
        return promos[f"{mc_version}-latest"]
    raise RuntimeError(f"No Forge build published for Minecraft {mc_version}")


def _forge_installer_url(mc_version: str, forge_version: str) -> str:
    full = f"{mc_version}-{forge_version}"
    return (f"{config.FORGE_MAVEN}/net/minecraftforge/forge/"
            f"{full}/forge-{full}-installer.jar")


def _write_dummy_launcher_profiles(game_dir: Path) -> None:
    # The Forge installer refuses to run a client install without this file.
    lp = game_dir / "launcher_profiles.json"
    if not lp.exists():
        lp.write_text(json.dumps(
            {"profiles": {}, "settings": {}, "version": 3,
             "selectedProfile": None, "clientToken": "smoothclient"}), "utf-8")


def install_forge(mc_version: str, java_path: Path, game_dir: Path,
                  forge_version: Optional[str] = None, log: Log = None) -> dict:
    """Install Forge headlessly and return its merged-ready version JSON."""
    forge_version = forge_version or resolve_forge_version(mc_version)
    full = f"{mc_version}-{forge_version}"
    if log:
        log(f"Forge {full}: downloading installer ...")
    installer = config.CACHE_DIR / f"forge-{full}-installer.jar"
    download(_forge_installer_url(mc_version, forge_version), installer, log=log)

    game_dir.mkdir(parents=True, exist_ok=True)
    _write_dummy_launcher_profiles(game_dir)

    existing = {p.name for p in config.VERSIONS_DIR.glob("*") if p.is_dir()}

    if log:
        log("Forge: running headless installer (this can take a minute) ...")
    cmd = [str(java_path), "-Djava.awt.headless=true", "-jar", str(installer),
           "--install-client", str(game_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd=str(config.VERSIONS_DIR.parent))
    if log:
        for line in (proc.stdout or "").splitlines()[-12:]:
            log(f"  forge> {line}")
    if proc.returncode != 0:
        # Older Forge (<1.17) installers may need X11 / the ForgeInstallerHeadless
        # wrapper. Surface a clear message rather than failing silently.
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise RuntimeError(
            "Forge headless install failed (rc="
            f"{proc.returncode}). Newer MC versions install cleanly; very old "
            "Forge may need the headless wrapper. Installer said: " + " | ".join(tail))

    # Find the version folder Forge just created.
    new_dirs = [p for p in config.VERSIONS_DIR.glob("*")
                if p.is_dir() and p.name not in existing]
    candidate = None
    for d in new_dirs + list(config.VERSIONS_DIR.glob("*forge*")):
        jf = d / f"{d.name}.json"
        if jf.exists():
            data = json.loads(jf.read_text("utf-8"))
            if data.get("inheritsFrom") == mc_version or "forge" in d.name.lower():
                candidate = data
                break
    if candidate is None:
        raise RuntimeError("Forge installed but its version JSON was not found.")
    if log:
        log(f"Forge ready: {candidate.get('id')}")
    return candidate
