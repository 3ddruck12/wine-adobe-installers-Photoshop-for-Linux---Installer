# Changelog – Photoshop AppImage v3.0

## Überblick

Kompletter Rewrite des Projekts: Wine 11.1 als vorkompiliertes Bundle, kein Build beim User mehr, GUI auf Englisch, 25+ Bugs behoben.

---

## Architektur-Änderung

| Vorher (v2.x, Wine 10.0) | Nachher (v3.0, Wine 11.1) |
|---|---|
| User kompiliert Wine aus Source (~30–60 min) | Wine vorkompiliert im AppImage gebündelt |
| esync/fsync als manueller Patch | `inproc_sync` nativ in Wine 11.1 |
| Build scheitert mit Clang 18+ | Wine 11.1 kompiliert sauber |
| gcc, flex, bison, make beim User nötig | Nur `winetricks` als Abhängigkeit |
| GUI Deutsch/Englisch gemischt | Komplett Englisch |
| `--launch` nicht implementiert | Funktionierender Direct-Launch via `os.execvpe()` |

---

## PhotoshopInstaller.py – Komplett-Rewrite

**Entfernt:**
- `WineBuildThread` – kein Wine-Build mehr beim User
- `install_package()` mit `--break-system-packages` Hack (PEP 668 Verletzung)
- `DependencyChecker` für Build-Tools (gcc, flex, bison, make) – nicht mehr nötig
- Alle deutschen UI-Strings

**Neu / Gefixt:**

| Bug | Fix |
|---|---|
| `get_base_dir()` identisch für frozen/normal | Erkennt jetzt `$APPDIR` im AppImage-Kontext |
| `get_writable_wine_dir()` kein Existenz-Check | `get_wine_binary()` prüft AppImage → lokaler Build → System-Wine mit Existenz-Checks |
| `--launch` tut nichts (leere `pass`-Blöcke) | `direct_launch()` via `os.execvpe()` – ersetzt den Prozess direkt |
| `os.chdir()` im Build-Thread (globales CWD) | Komplett entfernt, `cwd=` Parameter in subprocess |
| `os.system()` Shell-Injection | Durch `subprocess.Popen([...])` / `subprocess.run([...])` ersetzt |
| `run_command()` verschluckt Output | Entfernt (kein Build mehr), alle Outputs werden geloggt |
| Keine Bestätigungsdialoge | `QMessageBox.question()` vor `deep_repair` und `clean_prefix` |
| `install_missing_deps` Race Condition (5s Timer) | Rekursiver Timer wartet auf Prozess-Ende, dann Recheck |
| Desktop-Dateien mit `0o755` | Korrekt auf `0o644` gesetzt |
| `setup_btn` sofort klickbar bei fehlenden Deps | Startet **deaktiviert**, wird erst bei erfüllten Dependencies freigeschaltet |
| `launch_photoshop` nur Photoshop 2021 Pfad | Sucht 2025 → 2024 → 2021, dann Glob-Fallback |
| Installer-Fehler nur nach stdout | Fehler werden im GUI-Log angezeigt via `log_signal` |
| `WineEnvironmentThread` ohne Timeout | Alle `subprocess.run()` Aufrufe haben Timeouts |
| Kein `WINESERVER` env gesetzt | `_make_env()` setzt `WINESERVER` und `WINEDLLPATH` automatisch |

**Neue Features:**
- `InstallerRunnerThread` – blockierungsfreie .exe Ausführung in eigenem QThread
- `_set_busy()` – deaktiviert alle Action-Buttons während einer Operation
- `_find_photoshop_exe()` – intelligente Suche nach Photoshop.exe mit Glob-Fallback
- Danger-Button-Styling für destruktive Aktionen (rot)
- `ensure_pyqt6()` – sauberer PyQt6-Check ohne `--break-system-packages`

---

## build_appimage.sh – Neues Build-Konzept

**Vorher:**
- Kopierte nur Wine-Source ins AppImage
- User musste Wine selbst kompilieren
- `python-standalone.tar.gz` Download nicht dokumentiert
- Doppelte AppRun-Erzeugung (Repo-Datei + dynamisch im Skript)
- `mogrify` als stille Abhängigkeit

**Nachher:**
- **Step 1:** Wine 11.1 wird mit `./configure --enable-win64 --disable-tests` kompiliert und gecacht
- **Step 2:** Nur das fertige Wine-Runtime (Binaries + Libs) wird ins AppImage kopiert, nicht der Source-Tree
- **Step 3:** Python-Standalone wird extrahiert, PyQt6 hinein installiert
- **Step 4:** Installer-Dateien werden kopiert
- **Step 5:** AppRun wird generiert (setzt auch `WINEDLLPATH`)
- **Step 6:** Desktop-File mit korrekten Permissions (644)
- **Step 7:** linuxdeploy bündelt System-Libraries (optional)
- **Step 8:** appimagetool erzeugt das finale AppImage
- `python-standalone.tar.gz` Download-URL vollständig dokumentiert
- `mogrify` als **optional** markiert
- `set -euo pipefail` für robuste Fehlerbehandlung
- Build-Parallelismus auf max 8 begrenzt

---

## version_configs.json – Bereinigt

**Vorher:**
```json
{
  "wine_version": "fix-dropdowns",
  "winetricks": ["msxml3", "mshtml", "vcruntimes", "atmlib", "gdiplus"],
  "patches": ["js_xml_CDATA_fix", "ie9_emulation"]
}
```

**Nachher:**
```json
{
  "wine_version": "11.1",
  "winetricks": ["msxml3", "msxml6", "vcrun2019", "atmlib", "gdiplus", "corefonts"]
}
```

- `wine_version` → `"11.1"` statt `"fix-dropdowns"`
- Tote `patches`-Einträge **entfernt** (wurden im Code nie referenziert)
- `mshtml` entfernt (nicht nötig für Photoshop)
- `msxml6` hinzugefügt (Adobe-Installer benötigt es)
- `vcruntimes` → `vcrun2019` / `vcrun2022` (spezifisch statt Mega-Paket)
- `corefonts` hinzugefügt (verhindert UI-Rendering-Probleme)

---

## AppRun – Aktualisiert

- Setzt `$WINEDLLPATH` für gebundeltes Wine
- `$PATH` enthält jetzt sowohl Python als auch Wine-Binaries
- Verwendet `exec` statt einfachen Aufruf (spart einen Prozess)
- Saubere Fallback-Defaults für `$LD_LIBRARY_PATH`, `$PYTHONPATH`, `$WINEDLLPATH` mit `${VAR:-}`

---

## Dateien

| Datei | Status | Zeilen vorher → nachher |
|---|---|---|
| `PhotoshopInstaller.py` | Komplett-Rewrite | 976 → ~580 |
| `build_appimage.sh` | Komplett-Rewrite | ~80 → ~160 |
| `version_configs.json` | Überarbeitet | 16 → 14 |
| `AppRun` | Wird beim Build generiert | 10 → 13 |
| `photoshop.desktop` | Wird beim Build generiert | 6 → 7 |
| `PhotoshopInstaller.py.bak` | Backup der alten Version | – |
