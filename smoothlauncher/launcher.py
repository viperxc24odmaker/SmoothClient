"""Build the final java command (classpath, JVM args, game args with Mojang's
placeholder substitution) and launch Minecraft."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from . import config
from .accounts import Account
from .instances import Instance
from .installer import Resolved
from .utils import rules_allow

Log = Optional[Callable[[str], None]]


def _substitute(value: str, repl: dict) -> str:
    for k, v in repl.items():
        value = value.replace("${" + k + "}", str(v))
    return value


def _expand_args(arg_list, repl: dict, features: dict) -> list[str]:
    """Expand a modern `arguments` array (strings or {rules,value} objects)."""
    out: list[str] = []
    for item in arg_list:
        if isinstance(item, str):
            out.append(_substitute(item, repl))
        elif isinstance(item, dict):
            if not rules_allow(item.get("rules"), features):
                continue
            val = item.get("value", [])
            vals = [val] if isinstance(val, str) else val
            out.extend(_substitute(v, repl) for v in vals)
    return out


def build_command(inst: Instance, acc: Account, res: Resolved) -> list[str]:
    vjson = res.vjson
    classpath = os.pathsep.join(str(p) for p in res.classpath)

    repl = {
        "auth_player_name": acc.username,
        "version_name": res.version_id,
        "game_directory": str(inst.dir),
        "assets_root": str(config.ASSETS_DIR),
        "assets_index_name": res.assets_index,
        "auth_uuid": acc.undashed,
        "auth_access_token": acc.access_token,
        "auth_xuid": "",
        "clientid": "",
        "user_type": acc.user_type,
        "version_type": vjson.get("type", "release"),
        "natives_directory": str(res.natives_dir),
        "launcher_name": config.LAUNCHER_NAME,
        "launcher_version": config.LAUNCHER_VERSION,
        "classpath": classpath,
        "library_directory": str(config.LIBRARIES_DIR),
        "classpath_separator": os.pathsep,
        "resolution_width": "854",
        "resolution_height": "480",
    }
    features = {"is_demo_user": False, "has_custom_resolution": False}

    cmd: list[str] = [str(res.java_path)]

    # Memory + user extra args
    cmd.append(f"-Xmx{inst.memory_mb}M")
    cmd.append("-Xms512M")
    if inst.extra_jvm_args.strip():
        cmd.extend(inst.extra_jvm_args.split())

    args = vjson.get("arguments")
    if args and "jvm" in args:
        cmd.extend(_expand_args(args["jvm"], repl, features))
    else:
        # Legacy versions: no jvm arg array -> supply the essentials.
        cmd.append(f"-Djava.library.path={res.natives_dir}")
        cmd.extend(["-cp", classpath])

    cmd.append(vjson["mainClass"])

    if args and "game" in args:
        cmd.extend(_expand_args(args["game"], repl, features))
    elif vjson.get("minecraftArguments"):
        cmd.extend(_substitute(vjson["minecraftArguments"], repl).split())

    return cmd


def launch(inst: Instance, acc: Account, res: Resolved, log: Log = None) -> subprocess.Popen:
    log = log or (lambda *_: None)
    cmd = build_command(inst, acc, res)
    log("Launch command:")
    log("  " + " ".join(cmd[:6]) + " ... (" + str(len(cmd)) + " args)")
    inst.dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        cmd, cwd=str(inst.dir),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    log(f"Minecraft started (pid {proc.pid}) 🎮")
    return proc
