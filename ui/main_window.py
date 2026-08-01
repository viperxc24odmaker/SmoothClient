"""Smooth Client Launcher — main window."""
from __future__ import annotations
import webbrowser

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QSpinBox, QListWidget, QListWidgetItem, QFrame,
    QTextEdit, QCheckBox, QInputDialog, QMessageBox, QProgressBar, QFormLayout,
    QTabWidget,
)

from smoothlauncher import config, manifest, settings
from smoothlauncher.accounts import AccountStore
from smoothlauncher.instances import Instance, InstanceStore
from smoothlauncher.mods import ModResult
from .theme import QSS
from .worker import (LaunchWorker, MicrosoftWorker, ModSearchWorker,
                     ModInstallWorker)


class VersionsWorker(QThread):
    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, snapshots: bool):
        super().__init__()
        self.snapshots = snapshots

    def run(self):
        try:
            self.done.emit([v["id"] for v in manifest.list_versions(self.snapshots)])
        except Exception as e:
            self.failed.emit(str(e))


def _card(obj_name="card") -> QFrame:
    f = QFrame()
    f.setObjectName(obj_name)
    return f


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smooth Client Launcher")
        self.resize(1040, 680)
        self.accounts = AccountStore()
        self.instances = InstanceStore()
        self._launch_worker = None
        self._ms_worker = None
        self._vers_worker = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        tabs = QTabWidget()
        tabs.addTab(self._build_play_tab(), "Play")
        tabs.addTab(self._build_mods_tab(), "Mods")
        tabs.currentChanged.connect(lambda _i: self._refresh_mod_instances())
        outer.addWidget(tabs, 1)
        outer.addWidget(self._build_console(), 0)

        self.setStyleSheet(QSS)
        self._refresh_accounts()
        self._refresh_instances()
        self._load_versions()
        self._new_instance()

    def _build_play_tab(self) -> QWidget:
        w = QWidget()
        body = QHBoxLayout(w)
        body.setContentsMargins(0, 8, 0, 0)
        body.setSpacing(14)
        body.addWidget(self._build_instance_panel(), 0)
        body.addWidget(self._build_detail_panel(), 1)
        return w

    # ---------------- header ----------------
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel()
        title.setObjectName("title")
        title.setText('<span style="color:#38e1ff">Smooth</span> Client')
        row.addWidget(title)
        row.addStretch(1)

        row.addWidget(QLabel("Account:"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(190)
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        row.addWidget(self.account_combo)

        b_off = QPushButton("+ Offline")
        b_off.clicked.connect(self._add_offline)
        row.addWidget(b_off)
        b_ms = QPushButton("+ Microsoft")
        b_ms.clicked.connect(self._add_microsoft)
        row.addWidget(b_ms)
        return row

    # ---------------- instances list ----------------
    def _build_instance_panel(self) -> QFrame:
        card = _card()
        card.setFixedWidth(270)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(QLabel("Instances"))
        self.instance_list = QListWidget()
        self.instance_list.currentItemChanged.connect(self._on_instance_selected)
        lay.addWidget(self.instance_list, 1)
        btns = QHBoxLayout()
        b_new = QPushButton("New")
        b_new.clicked.connect(self._new_instance)
        b_del = QPushButton("Delete")
        b_del.setObjectName("danger")
        b_del.clicked.connect(self._delete_instance)
        btns.addWidget(b_new)
        btns.addWidget(b_del)
        lay.addLayout(btns)
        return card

    # ---------------- detail / editor ----------------
    def _build_detail_panel(self) -> QFrame:
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        head = QLabel("Instance")
        head.setObjectName("accent")
        lay.addWidget(head)

        form = QFormLayout()
        form.setSpacing(10)

        self.f_name = QLineEdit()
        form.addRow("Name", self.f_name)

        vrow = QHBoxLayout()
        self.f_version = QComboBox()
        self.f_version.setMinimumWidth(180)
        self.f_snapshots = QCheckBox("snapshots")
        self.f_snapshots.stateChanged.connect(lambda _: self._load_versions())
        vrow.addWidget(self.f_version, 1)
        vrow.addWidget(self.f_snapshots)
        vwrap = QWidget()
        vwrap.setLayout(vrow)
        form.addRow("Minecraft", vwrap)

        self.f_loader = QComboBox()
        self.f_loader.addItems(["vanilla", "fabric", "forge"])
        self.f_loader.currentTextChanged.connect(self._on_loader_changed)
        form.addRow("Loader", self.f_loader)

        self.f_loader_ver = QLineEdit()
        self.f_loader_ver.setPlaceholderText("latest (auto)")
        form.addRow("Loader version", self.f_loader_ver)

        self.f_perf = QComboBox()
        self.f_perf.addItem("None", "none")
        self.f_perf.addItem("VulkanMod (big FPS)", "vulkanmod")
        self.f_perf.addItem("Sodium + Lithium", "sodium")
        form.addRow("Performance", self.f_perf)

        self.f_mem = QSpinBox()
        self.f_mem.setRange(1024, 32768)
        self.f_mem.setSingleStep(512)
        self.f_mem.setSuffix(" MB")
        self.f_mem.setValue(config.DEFAULT_MEMORY_MB)
        form.addRow("Memory", self.f_mem)

        self.f_java = QLineEdit()
        self.f_java.setPlaceholderText("auto (bundled Mojang JRE)")
        form.addRow("Java path", self.f_java)

        lay.addLayout(form)
        lay.addStretch(1)

        actions = QHBoxLayout()
        b_save = QPushButton("Save Instance")
        b_save.clicked.connect(self._save_instance)
        actions.addWidget(b_save)
        actions.addStretch(1)
        self.b_launch = QPushButton("▶  Launch")
        self.b_launch.setObjectName("primary")
        self.b_launch.clicked.connect(self._launch)
        actions.addWidget(self.b_launch)
        lay.addLayout(actions)
        return card

    # ---------------- mods browser ----------------
    def _build_mods_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)

        bar = _card("panel2")
        bar_l = QHBoxLayout(bar)
        bar_l.setContentsMargins(12, 10, 12, 10)

        bar_l.addWidget(QLabel("Instance:"))
        self.mod_instance = QComboBox()
        self.mod_instance.setMinimumWidth(160)
        bar_l.addWidget(self.mod_instance)

        bar_l.addWidget(QLabel("Source:"))
        self.mod_source = QComboBox()
        self.mod_source.addItem("Modrinth", "modrinth")
        self.mod_source.addItem("CurseForge", "curseforge")
        self.mod_source.currentIndexChanged.connect(self._on_source_changed)
        bar_l.addWidget(self.mod_source)

        self.mod_query = QLineEdit()
        self.mod_query.setPlaceholderText("Search mods…")
        self.mod_query.returnPressed.connect(self._mod_search)
        bar_l.addWidget(self.mod_query, 1)

        b_search = QPushButton("Search")
        b_search.setObjectName("primary")
        b_search.clicked.connect(self._mod_search)
        bar_l.addWidget(b_search)

        self.b_cf_key = QPushButton("Set CF key")
        self.b_cf_key.clicked.connect(self._set_cf_key)
        self.b_cf_key.setVisible(False)
        bar_l.addWidget(self.b_cf_key)
        lay.addWidget(bar)

        self.mod_results = QListWidget()
        lay.addWidget(self.mod_results, 1)

        self.mod_hint = QLabel("Pick an instance, search, then Install → drops the "
                               "right build into that instance's mods folder.")
        self.mod_hint.setObjectName("muted")
        lay.addWidget(self.mod_hint)
        return w

    def _refresh_mod_instances(self):
        if not hasattr(self, "mod_instance"):
            return
        keep = self.mod_instance.currentText()
        self.mod_instance.clear()
        for inst in self.instances.instances:
            self.mod_instance.addItem(f"{inst.name}  ({inst.mc_version}/{inst.loader})",
                                      inst.name)
        if keep:
            i = self.mod_instance.findText(keep)
            if i >= 0:
                self.mod_instance.setCurrentIndex(i)

    def _on_source_changed(self, _i):
        is_cf = self.mod_source.currentData() == "curseforge"
        self.b_cf_key.setVisible(is_cf)
        if is_cf and not settings.get_cf_key():
            self.mod_hint.setText("CurseForge needs a free API key from "
                                  "console.curseforge.com → click 'Set CF key'.")

    def _set_cf_key(self):
        key, ok = QInputDialog.getText(self, "CurseForge API key",
                                       "Paste your key from console.curseforge.com:")
        if ok and key.strip():
            settings.set_cf_key(key.strip())
            self.log("CurseForge API key saved.")
            self.mod_hint.setText("Key saved — search away.")

    def _current_mod_instance(self) -> Instance | None:
        name = self.mod_instance.currentData()
        return self.instances.get(name) if name else None

    def _mod_search(self):
        inst = self._current_mod_instance()
        if not inst:
            QMessageBox.warning(self, "No instance",
                                "Create/select an instance first (Play tab).")
            return
        query = self.mod_query.text().strip()
        source = self.mod_source.currentData()
        if source == "curseforge" and not settings.get_cf_key():
            self._set_cf_key()
            if not settings.get_cf_key():
                return
        self.mod_results.clear()
        self.mod_results.addItem("Searching…")
        self._mod_search_worker = ModSearchWorker(source, query, inst.mc_version, inst.loader)
        self._mod_search_worker.done.connect(self._mod_results_ready)
        self._mod_search_worker.failed.connect(self._mod_search_failed)
        self._mod_search_worker.start()

    def _mod_search_failed(self, err: str):
        self.mod_results.clear()
        self.mod_results.addItem(f"Search failed: {err}")

    def _mod_results_ready(self, results: list):
        self.mod_results.clear()
        if not results:
            self.mod_results.addItem("No results.")
            return
        for r in results:
            self._add_mod_row(r)

    def _add_mod_row(self, r: ModResult):
        item = QListWidgetItem()
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 8, 10, 8)
        info = QVBoxLayout()
        title = QLabel(f"<b>{r.name}</b>  <span style='color:#8b98a9'>by {r.author}</span>")
        desc = QLabel(r.description[:110] + ("…" if len(r.description) > 110 else ""))
        desc.setObjectName("muted")
        meta = QLabel(f"{r.source} · {r.downloads:,} downloads")
        meta.setObjectName("muted")
        info.addWidget(title)
        info.addWidget(desc)
        info.addWidget(meta)
        rl.addLayout(info, 1)
        b = QPushButton("Install")
        b.setObjectName("primary")
        b.clicked.connect(lambda _=False, res=r: self._install_mod(res))
        rl.addWidget(b)
        item.setSizeHint(row.sizeHint())
        self.mod_results.addItem(item)
        self.mod_results.setItemWidget(item, row)

    def _install_mod(self, r: ModResult):
        inst = self._current_mod_instance()
        if not inst:
            return
        self.log(f"Installing {r.name} → {inst.name} …")
        self._mod_install_worker = ModInstallWorker(r, inst.mc_version, inst.loader, inst.mods_dir)
        self._mod_install_worker.log.connect(self.log)
        self._mod_install_worker.result.connect(self._mod_install_done)
        self._mod_install_worker.start()

    def _mod_install_done(self, status: str, detail: str, name: str):
        if status == "ok":
            self.log(f"✅ Installed {name}: {detail}")
        elif status == "manual":
            self.log(f"⚠ {name}: author disabled API downloads — opening page.")
            webbrowser.open(detail)
            QMessageBox.information(
                self, "Manual download",
                f"{name} can't be downloaded via the API (author's choice).\n"
                "Its CurseForge page was opened — download the jar and drop it in "
                "the instance's mods folder.")
        else:
            self.log(f"[mod] {name}: {detail}")

    # ---------------- console ----------------
    def _build_console(self) -> QFrame:
        card = _card()
        card.setFixedHeight(190)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 12)
        top = QHBoxLayout()
        top.addWidget(QLabel("Console"))
        top.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedWidth(200)
        top.addWidget(self.progress)
        lay.addLayout(top)
        self.console = QTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        lay.addWidget(self.console, 1)
        return card

    # ================= helpers =================
    def log(self, msg: str):
        self.console.append(msg)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum())

    def _busy(self, on: bool):
        self.progress.setVisible(on)
        self.b_launch.setEnabled(not on)

    # ================= accounts =================
    def _refresh_accounts(self):
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for a in self.accounts.accounts:
            tag = "MS" if a.kind == "microsoft" else "offline"
            self.account_combo.addItem(f"{a.username}  ({tag})", a.uuid)
        sel = self.accounts.selected
        if sel:
            idx = self.account_combo.findData(sel)
            if idx >= 0:
                self.account_combo.setCurrentIndex(idx)
        self.account_combo.blockSignals(False)

    def _on_account_changed(self, _idx):
        uuid = self.account_combo.currentData()
        if uuid:
            self.accounts.selected = uuid
            self.accounts.save()

    def _add_offline(self):
        name, ok = QInputDialog.getText(self, "Offline account", "Username:")
        if ok and name.strip():
            self.accounts.add_offline(name.strip())
            self._refresh_accounts()
            self.log(f"Added offline account: {name.strip()}")

    def _add_microsoft(self):
        if config.MS_CLIENT_ID.startswith("PASTE"):
            QMessageBox.warning(
                self, "Azure client ID needed",
                "Set your Azure app's client ID first.\n\n"
                "Register a free public-client app at portal.azure.com, enable "
                "device-code flow, and put its ID in smoothlauncher/config.py "
                "(MS_CLIENT_ID) or the SMOOTH_MS_CLIENT_ID env var.")
            return
        self.log("Starting Microsoft sign-in ...")
        self._ms_worker = MicrosoftWorker()
        self._ms_worker.code_ready.connect(self._show_ms_code)
        self._ms_worker.log.connect(self.log)
        self._ms_worker.signed_in.connect(self._ms_done)
        self._ms_worker.failed.connect(lambda e: self.log(f"[MS error] {e}"))
        self._ms_worker.start()

    def _show_ms_code(self, device: dict):
        uri = device.get("verification_uri", "https://microsoft.com/link")
        code = device.get("user_code", "")
        webbrowser.open(uri)
        QGuiApplication.clipboard().setText(code)
        QMessageBox.information(
            self, "Sign in to Microsoft",
            f"1. A browser opened to:\n   {uri}\n\n"
            f"2. Enter this code (copied to clipboard):\n\n        {code}\n\n"
            "Waiting for you to finish ...")

    def _ms_done(self, acc):
        self.accounts.add(acc)
        self._refresh_accounts()
        self.log(f"Microsoft account added: {acc.username}")

    # ================= instances =================
    def _refresh_instances(self):
        self.instance_list.clear()
        for inst in self.instances.instances:
            item = QListWidgetItem(f"{inst.name}\n{inst.mc_version} · {inst.loader}")
            item.setData(Qt.ItemDataRole.UserRole, inst.name)
            self.instance_list.addItem(item)
        self._refresh_mod_instances()

    def _on_instance_selected(self, cur, _prev):
        if not cur:
            return
        inst = self.instances.get(cur.data(Qt.ItemDataRole.UserRole))
        if inst:
            self._load_into_form(inst)

    def _load_into_form(self, inst: Instance):
        self.f_name.setText(inst.name)
        idx = self.f_version.findText(inst.mc_version)
        if idx >= 0:
            self.f_version.setCurrentIndex(idx)
        self.f_loader.setCurrentText(inst.loader)
        self.f_loader_ver.setText(inst.loader_version)
        pidx = self.f_perf.findData(inst.performance)
        self.f_perf.setCurrentIndex(pidx if pidx >= 0 else 0)
        self.f_mem.setValue(inst.memory_mb)
        self.f_java.setText(inst.java_path)
        self._on_loader_changed(inst.loader)

    def _new_instance(self):
        self.instance_list.clearSelection()
        self.f_name.setText("New Instance")
        self.f_loader.setCurrentText("vanilla")
        self.f_loader_ver.clear()
        self.f_perf.setCurrentIndex(0)
        self.f_mem.setValue(config.DEFAULT_MEMORY_MB)
        self.f_java.clear()
        self._on_loader_changed("vanilla")

    def _on_loader_changed(self, loader: str):
        is_fabric = loader == "fabric"
        self.f_perf.setEnabled(is_fabric)
        if not is_fabric:
            self.f_perf.setCurrentIndex(0)

    def _collect_form(self) -> Instance | None:
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Give the instance a name.")
            return None
        if not self.f_version.currentText():
            QMessageBox.warning(self, "No version", "Pick a Minecraft version.")
            return None
        return Instance(
            name=name,
            mc_version=self.f_version.currentText(),
            loader=self.f_loader.currentText(),
            loader_version=self.f_loader_ver.text().strip(),
            performance=self.f_perf.currentData() or "none",
            memory_mb=self.f_mem.value(),
            java_path=self.f_java.text().strip(),
        )

    def _save_instance(self):
        inst = self._collect_form()
        if inst:
            self.instances.add(inst)
            self._refresh_instances()
            self.log(f"Saved instance: {inst.name}")

    def _delete_instance(self):
        cur = self.instance_list.currentItem()
        if not cur:
            return
        name = cur.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete instance '{name}'?") \
                == QMessageBox.StandardButton.Yes:
            self.instances.remove(name)
            self._refresh_instances()
            self._new_instance()

    # ================= versions =================
    def _load_versions(self):
        self._vers_worker = VersionsWorker(self.f_snapshots.isChecked())
        self._vers_worker.done.connect(self._versions_ready)
        self._vers_worker.failed.connect(lambda e: self.log(f"[versions] {e}"))
        self._vers_worker.start()

    def _versions_ready(self, versions: list):
        keep = self.f_version.currentText()
        self.f_version.clear()
        self.f_version.addItems(versions)
        if keep:
            i = self.f_version.findText(keep)
            if i >= 0:
                self.f_version.setCurrentIndex(i)

    # ================= launch =================
    def _launch(self):
        inst = self._collect_form()
        if not inst:
            return
        acc = self.accounts.get_selected()
        if not acc:
            QMessageBox.warning(self, "No account",
                                "Add and select an account first.")
            return
        self.instances.add(inst)
        self._refresh_instances()
        self.console.clear()
        self._busy(True)
        self.log(f"Preparing '{inst.name}' ({inst.mc_version}, {inst.loader}) ...")
        self._launch_worker = LaunchWorker(inst, acc)
        self._launch_worker.log.connect(self.log)
        self._launch_worker.finished_ok.connect(lambda: self._busy(False))
        self._launch_worker.failed.connect(self._launch_failed)
        self._launch_worker.start()

    def _launch_failed(self, err: str):
        self._busy(False)
        self.log(f"[ERROR] {err}")
        QMessageBox.critical(self, "Launch failed", err)
