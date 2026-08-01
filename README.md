# Smooth Client Launcher — Phase 1 (Core)

A browser-CI-built Windows Minecraft launcher. Vanilla + Fabric + Forge, offline
and Microsoft accounts (real UUIDs), per-instance game dirs, a per-instance
performance picker, and a built-in **Modrinth + CurseForge mod browser**. Built to
your workflow: **push to GitHub → Actions builds the `.exe` → download the
artifact.** No local dev needed.

> Phase 1 (core) + Phase 3 (mod browser) are both in this repo. Phase 2 = the
> **Smooth Client** Fabric mod (28 modules, Right-Shift ClickGUI, drag+snap HUD
> editor, dark glassy cyan theme) is still to come — say "go phase 2" when ready.

---

## Build it (GitHub Actions → .exe)

1. Make a new GitHub repo and add these files.
   ⚠️ **Create `.github/workflows/build.yml` by hand in GitHub's web editor** —
   drag-and-drop upload skips hidden dot-folders (you know this one 😅).
2. Push to `main` (or run the workflow manually via **Actions → Run workflow**).
3. When it finishes, grab **`SmoothClientLauncher-windows`** from the run's
   Artifacts. Inside is `SmoothClientLauncher.exe`.

Workflow: Windows runner → Python 3.11 → PyInstaller `--onefile --windowed`.

## Use it

- **Add an account** (top right): *+ Offline* (username only) or *+ Microsoft*.
- **New instance**: name, Minecraft version, loader (vanilla/fabric/forge),
  performance pack (Fabric only), memory, optional Java path.
- **▶ Launch**: installs everything needed (libraries, assets, natives, the right
  Java runtime, the loader), then starts the game. Progress streams to the console.

Everything lives under `%APPDATA%/SmoothClientLauncher`. The heavy shared game
files (versions/libraries/assets) are downloaded once and reused by all instances;
each instance keeps its own `mods/`, `saves/`, `config/`, `resourcepacks/`.

---

## Microsoft login setup (one-time)

Mojang requires each launcher to use its **own** Azure app ID. Free to make:

1. https://portal.azure.com → **App registrations** → **New registration**.
2. Supported accounts: *Personal Microsoft accounts*. No redirect URI needed.
3. **Authentication → Advanced → Allow public client flows → Yes**.
4. Copy the **Application (client) ID** and put it in one of:
   - `smoothlauncher/config.py` → `MS_CLIENT_ID`, or
   - the `SMOOTH_MS_CLIENT_ID` environment variable.

Offline accounts work with zero setup and generate the same UUID Minecraft
servers compute (`UUID.nameUUIDFromBytes("OfflinePlayer:<name>")`).

## Loader notes

- **Fabric** — clean. Pulls the ready profile from `meta.fabricmc.net`, auto-picks
  the latest stable loader (or pin one in *Loader version*).
- **Forge** — the tricky one. Runs Forge's **own** installer headlessly
  (`SimpleInstaller --install-client`) because Forge patches the client with
  binary processors that need a JVM. Modern versions (≈1.17+) install cleanly.
  **Very old Forge (<1.17)** may need the `ForgeInstallerHeadless` wrapper — this
  is the piece most likely to need a tweak on your first real test, since it can't
  be verified without launching MC.

## Performance picker (Fabric only)

Per instance: **VulkanMod** (your setup, big FPS), **Sodium + Lithium**, or none.
Mods are fetched from Modrinth's open API for the instance's exact MC version and
dropped into that instance's `mods/` folder.

## Mod browser (Modrinth + CurseForge)

The **Mods** tab: pick an instance, choose a source, search, and **Install** →
the newest build matching that instance's MC version + loader drops straight into
its `mods/` folder.

- **Modrinth** — open API, nothing to set up.
- **CurseForge** — needs a free API key from **console.curseforge.com**. Click
  **Set CF key** in the Mods tab (or set `SMOOTH_CF_API_KEY`). Some mods have
  third-party downloads disabled by their author — those can't be fetched via the
  API, so the launcher opens the mod's page for a manual grab into `mods/`.

---

## Layout

```
smoothlauncher/
  config.py       paths + endpoints
  utils.py        os detection, rules, maven paths, downloads, version merge
  manifest.py     Mojang version manifest + version JSON
  gamefiles.py    client jar, libraries, natives, assets
  java.py         Mojang JRE download / system Java fallback
  loaders.py      Fabric (meta API) + Forge (headless installer)
  performance.py  VulkanMod / Sodium+Lithium via Modrinth
  mods.py         Modrinth + CurseForge search/install
  settings.py     CurseForge API key store
  accounts.py     offline UUID + Microsoft device-code flow
  instances.py    instance model + store
  installer.py    resolve + download everything for an instance
  launcher.py     build java command (arg substitution) + run
ui/
  theme.py        dark glassy cyan stylesheet
  worker.py       QThreads (install/launch, MS sign-in)
  main_window.py  the window
main.py           entry point
```
