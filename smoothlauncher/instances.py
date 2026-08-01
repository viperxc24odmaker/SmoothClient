"""Instance model + store. An instance = a version + loader + its own
game directory (saves/mods/resourcepacks/config) + performance choice."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from . import config


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-") or "instance"


@dataclass
class Instance:
    name: str
    mc_version: str
    loader: str = "vanilla"          # vanilla | fabric | forge
    loader_version: str = ""         # optional pin; blank = latest
    performance: str = "none"        # none | vulkanmod | sodium  (fabric only)
    memory_mb: int = config.DEFAULT_MEMORY_MB
    java_path: str = ""              # blank = auto
    extra_jvm_args: str = ""
    smooth_client: bool = True       # phase 2 hook: inject Smooth Client on fabric
    installed_version_id: str = ""   # resolved id actually launched (cache)

    @property
    def dir(self) -> Path:
        return config.INSTANCES_DIR / _slug(self.name)

    @property
    def mods_dir(self) -> Path:
        return self.dir / "mods"

    def ensure_dirs(self):
        for sub in ("", "mods", "config", "saves", "resourcepacks"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)


class InstanceStore:
    def __init__(self):
        self.instances: list[Instance] = []
        self.load()

    @property
    def _file(self) -> Path:
        return config.BASE_DIR / "instances.json"

    def load(self):
        if self._file.exists():
            raw = json.loads(self._file.read_text("utf-8"))
            self.instances = [Instance(**i) for i in raw]

    def save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps([asdict(i) for i in self.instances], indent=2), "utf-8")

    def add(self, inst: Instance):
        self.instances = [i for i in self.instances if i.name != inst.name]
        self.instances.append(inst)
        inst.ensure_dirs()
        self.save()

    def remove(self, name: str):
        self.instances = [i for i in self.instances if i.name != name]
        self.save()

    def get(self, name: str) -> Optional[Instance]:
        return next((i for i in self.instances if i.name == name), None)
