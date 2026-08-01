"""Background workers so install/launch and Microsoft sign-in never block the UI."""
from __future__ import annotations
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from smoothlauncher import installer, launcher, accounts, mods
from smoothlauncher.instances import Instance
from smoothlauncher.accounts import Account
from smoothlauncher.mods import ModResult


class LaunchWorker(QThread):
    log = pyqtSignal(str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, inst: Instance, acc: Account):
        super().__init__()
        self.inst = inst
        self.acc = acc

    def run(self):
        try:
            res = installer.resolve_and_install(self.inst, log=self.log.emit)
            proc = launcher.launch(self.inst, self.acc, res, log=self.log.emit)
            self.finished_ok.emit()
            # stream the game log
            if proc.stdout:
                for line in proc.stdout:
                    self.log.emit(line.rstrip())
        except Exception as e:
            self.failed.emit(str(e))


class MicrosoftWorker(QThread):
    """Runs the device-code flow. Emits the code prompt, then the finished account."""
    code_ready = pyqtSignal(dict)
    log = pyqtSignal(str)
    signed_in = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            device = accounts.start_device_code()
            self.code_ready.emit(device)
            token = accounts.poll_for_token(device, log=self.log.emit)
            acc = accounts.complete_microsoft(token, log=self.log.emit)
            self.signed_in.emit(acc)
        except Exception as e:
            self.failed.emit(str(e))


class ModSearchWorker(QThread):
    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, source: str, query: str, mc_version: str, loader: str):
        super().__init__()
        self.source, self.query = source, query
        self.mc_version, self.loader = mc_version, loader

    def run(self):
        try:
            self.done.emit(mods.search(self.source, self.query, self.mc_version, self.loader))
        except Exception as e:
            self.failed.emit(str(e))


class ModInstallWorker(QThread):
    log = pyqtSignal(str)
    result = pyqtSignal(str, str, str)   # status, detail, mod_name

    def __init__(self, mod: ModResult, mc_version: str, loader: str, mods_dir):
        super().__init__()
        self.mod = mod
        self.mc_version, self.loader = mc_version, loader
        self.mods_dir = mods_dir

    def run(self):
        try:
            status, detail = mods.install(
                self.mod, self.mc_version, self.loader, self.mods_dir, log=self.log.emit)
            self.result.emit(status, detail, self.mod.name)
        except Exception as e:
            self.result.emit("error", str(e), self.mod.name)
