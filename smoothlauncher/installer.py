"""Resolve an instance to a fully-installed, launch-ready state:
version JSON (merged with loader if needed) + client jar + libraries + natives
+ assets + Java + performance mods.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import config, manifest, gamefiles, java as javamod, loaders, performance
from .instances import Instance
from .utils import merge_versions

Log = Optional[Callable[[str], None]]


@dataclass
class Resolved:
    vjson: dict
    version_id: str
    client_jar: Path
    classpath: list
    natives_dir: Path
    assets_index: str
    java_path: Path


def resolve_and_install(inst: Instance, log: Log = None) -> Resolved:
    log = log or (lambda *_: None)
    config.ensure_dirs()
    inst.ensure_dirs()

    log(f"Loading Minecraft {inst.mc_version} ...")
    vanilla = manifest.get_version_json(inst.mc_version)

    # Java first (Forge installer needs it).
    java_path = javamod.resolve_java(vanilla, override=inst.java_path or None, log=log)
    log(f"Java: {java_path}")

    # Loader merge.
    if inst.loader == "fabric":
        profile = loaders.fabric_profile(inst.mc_version, inst.loader_version or None, log=log)
        vjson = merge_versions(vanilla, profile)
    elif inst.loader == "forge":
        forge_json = loaders.install_forge(
            inst.mc_version, java_path, inst.dir, inst.loader_version or None, log=log)
        vjson = merge_versions(vanilla, forge_json)
    else:
        vjson = vanilla
    version_id = vjson.get("id", inst.mc_version)

    # Client jar always comes from vanilla downloads.
    log("Downloading client jar ...")
    client_jar = gamefiles.download_client_jar(vanilla, log=log)

    log("Resolving libraries ...")
    classpath, native_jars = gamefiles.collect_libraries(vjson, log=log)

    log("Extracting natives ...")
    natives_dir = config.VERSIONS_DIR / version_id / "natives"
    gamefiles.extract_natives(native_jars, natives_dir, log=log)

    log("Downloading assets ...")
    assets_index = gamefiles.download_assets(vjson, log=log)

    # Performance pack (Fabric only).
    if inst.loader == "fabric" and inst.performance != "none":
        log(f"Installing performance pack: {inst.performance} ...")
        performance.install_pack(inst.performance, inst.mc_version, inst.mods_dir, log=log)

    inst.installed_version_id = version_id

    classpath.append(client_jar)
    return Resolved(
        vjson=vjson, version_id=version_id, client_jar=client_jar,
        classpath=classpath, natives_dir=natives_dir,
        assets_index=assets_index, java_path=java_path,
    )
