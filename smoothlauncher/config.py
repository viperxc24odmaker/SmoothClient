"""Central config: launcher paths, API endpoints, constants."""
from __future__ import annotations
import os
import sys
from pathlib import Path

APP_NAME = "SmoothClientLauncher"
LAUNCHER_NAME = "SmoothClient"
LAUNCHER_VERSION = "1.0.0"


def _base_dir() -> Path:
    """Root data dir. On Windows -> %APPDATA%/SmoothClientLauncher."""
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(root) / APP_NAME


BASE_DIR = _base_dir()
# Shared game data (versions, libraries, assets) lives once and is reused by every instance.
GAME_DIR = BASE_DIR / "game"
VERSIONS_DIR = GAME_DIR / "versions"
LIBRARIES_DIR = GAME_DIR / "libraries"
ASSETS_DIR = GAME_DIR / "assets"
RUNTIMES_DIR = BASE_DIR / "runtimes"          # downloaded Java runtimes
INSTANCES_DIR = BASE_DIR / "instances"        # per-instance saves/mods/configs
CACHE_DIR = BASE_DIR / "cache"

ACCOUNTS_FILE = BASE_DIR / "accounts.json"
SETTINGS_FILE = BASE_DIR / "settings.json"

# ---- Endpoints (verified live) ------------------------------------------------
VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
RESOURCES_BASE = "https://resources.download.minecraft.net"
JAVA_RUNTIME_MANIFEST = (
    "https://launchermeta.mojang.com/v1/products/java-runtime/"
    "2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json"
)

FABRIC_META = "https://meta.fabricmc.net/v2"
FABRIC_MAVEN = "https://maven.fabricmc.net/"

FORGE_MAVEN = "https://maven.minecraftforge.net"
FORGE_PROMOTIONS = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"

MODRINTH_API = "https://api.modrinth.com/v2"

# ---- Microsoft OAuth (device-code flow) --------------------------------------
# You MUST register your own Azure "public client" app and paste its Application
# (client) ID here. Enable "Allow public client flows" and add the Live SDK /
# XboxLive.signin scope. Free: https://portal.azure.com -> App registrations.
MS_CLIENT_ID = os.environ.get("SMOOTH_MS_CLIENT_ID", "PASTE-YOUR-AZURE-CLIENT-ID")
MS_SCOPE = "XboxLive.signin offline_access"
MS_DEVICECODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
MS_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBL_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_AUTH_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"

DEFAULT_MEMORY_MB = 4096

USER_AGENT = f"{LAUNCHER_NAME}/{LAUNCHER_VERSION} (github.com/MakeForge)"


def ensure_dirs() -> None:
    for d in (BASE_DIR, GAME_DIR, VERSIONS_DIR, LIBRARIES_DIR, ASSETS_DIR,
              RUNTIMES_DIR, INSTANCES_DIR, CACHE_DIR,
              ASSETS_DIR / "objects", ASSETS_DIR / "indexes"):
        d.mkdir(parents=True, exist_ok=True)
