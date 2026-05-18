# Photoshop AppImage – Weiteres Vorgehen

Sammlung von Tipps, Patch-Ideen und Diagnose-Schritten, basierend auf Erkenntnissen
aus [sander110419/lightroom-cc-on-linux](https://github.com/sander110419/lightroom-cc-on-linux)
und der eigenen Codebase.

---

## 1. Was bereits eingebaut ist (Stand: 2026-05-18)

### Build / Wine (Hauptrepo, CI-tauglich)

| Fix | Ort | Wirkung |
|---|---|---|
| **Wine 11.9** | [`build_appimage.sh`](build_appimage.sh), GitHub Actions | Aktuelle stabile Wine-Basis (mfplat, d2d1, combase-Fixes vs. 11.1) |
| **MSXML3 CDATA / embedded `<?xml?>`** | `wine-patches/dlls/msxml3/embedded_xml_cdata.c` + `patches/0001-msxml3-embedded-xml-cdata.patch` | Adobe-Installer/XML: eingebettete Deklarationen und `*XMLData`-Inhalte (früher in `domdoc.c` für 11.1) |
| **MSHTML-Patches** | `wine-patches/dlls/mshtml/*` | JS/DOM/Events für Installer-Web-UI — bei Wine-Upgrade **gegen neuen Tree testen** |
| **Unified-Diff-Patches** | `wine-patches/patches/*.patch` | Werden nach `cp -af` mit `patch -p1` angewendet (z. B. Hook in `node.c`) |

**Wichtig:** Die alte `wine-patches/dlls/msxml3/domdoc.c` (Wine-11.1-API) darf **nicht** mehr
mit Wine 11.9 kombiniert werden — Build bricht mit `struct domnode has no member named 'node'`.
Der Adobe-Fix lebt jetzt in `parse_stream()` (Wine-11.9-`msxml3`), nicht in `doparse()`.

### Laufzeit (Hauptrepo heute)

| Fix | Wirkung |
|---|---|
| `apply_adobe_winver_overrides()` | win7-Mode für CC, IPCBroker, `node.exe`, … |
| `repair_vcrun_msvcp140()` | 64-Bit-`msvcp140.dll` aus Winetricks-Cache |

### Geplant / Roadmap (noch nicht in `PhotoshopInstaller.py`)

Diese Fixes aus dem Lightroom-Repo — Ziel: `apply_adobe_runtime_fixes()` idempotent beim Launch:

| Fix | Wirkung |
|---|---|
| `AdobeGrowthSDK.dll` → `.disabled` | Crash `SetThreadpoolTimerEx` vermeiden |
| Lowercase-Symlinks für Adobe DLLs/EXEs | Case-sensitive Imports (`agkernel.dll` etc.) |
| `dxvk.conf` + `DXVK_CONFIG_FILE` | CC-Login-Fenster (Dummy-Composition-Swapchain) |

---

## 2. Test-Reihenfolge nach Installation

1. **One-Click Setup** ausführen
2. Creative-Cloud-Installer / Photoshop-Installer laufen lassen
3. **Photoshop starten** → UI sollte zumindest erscheinen
4. **Golden Path testen:**
   - Bild öffnen (.jpg, .png, .psd)
   - Pinsel-Tool, Auswahl-Tool benutzen
   - Datei speichern
5. **Heikle Features testen** (hier hakt es erfahrungsgemäß):
   - Content-Aware Fill / Remove Tool
   - Filter Gallery
   - Neural Filters (falls vorhanden)
   - Datei → Öffnen-Dialog (kann durch CEF-Subprocess hängen)

Bei Crashes: **"Save Installation Log"** klicken → der relevante Wine-Output
zeigt meist eindeutig, welche DLL/API fehlt.

---

## 3. Wahrscheinliche Folge-Probleme & Lösungen

### 3.1 Wine 11.9 + Patch-Kompatibilität (erledigt / laufend prüfen)

**Status:** Upgrade **11.1 → 11.9** ist im Build und CI umgesetzt
(siehe [`CHANGELOG.md`](CHANGELOG.md) v3.10-alpha).

**CI-Lektion (2026-05-18):** `wine-patches/` per `cp -af` ersetzt ganze Dateien.
Nach jedem Wine-Major-Upgrade prüfen:

1. Kompiliert `dlls/msxml3`? (11.9: kein `domnode->node` mehr)
2. Schlagen `wine-patches/patches/*.patch` fehl? → `patch` im Build-Log
3. Noch relevant: `wine-patches/dlls/mshtml/*` — bei Fehlern analog portieren oder Diff-Patch

**Nächster Schritt nach grünem CI:** Installer durchspielen; MSXML-Fix wirkt bei
`loadXML` / `parse_stream` (Adobe-Setup-XML), nicht mehr über libxml-`doparse`.

**Offen (Lightroom-Repo):** mfplat/d2d1-Stubs — siehe 3.2–3.4; 11.9 bringt Basis-Fixes,
zusätzliche Adobe-Patches können trotzdem nötig sein.

---

### 3.2 mfplat.dll Patch (Content-Aware / Remove Tool)

**Symptom:** Prozess-Abort beim Benutzen von Remove Tool, Content-Aware Fill
oder Inhaltsbasierter Patch. Wine-Log zeigt:
```
err:module:import_dll Library mfplat.dll ... function MFCreateSampleCopierMFT not found
```

**Lösung A (einfach):** Ein-Zeilen-Patch in `dlls/mfplat/mfplat.spec`:
```
@ stdcall MFCreateSampleCopierMFT(ptr) mf.MFCreateSampleCopierMFT
```
Als `wine-patches/dlls/mfplat/mfplat.spec` (Vollständige Datei) **oder** als
`wine-patches/patches/0002-mfplat-….patch` (empfohlen bei Wine-Upgrade).
Build: zuerst `cp -af wine-patches/`, dann `patches/*.patch` — siehe
[`build_appimage.sh`](build_appimage.sh).

**Lösung B (komplex):** Vorgebauten patched `mfplat.dll` als Binary
mitliefern (siehe Lightroom-Repo `stubs/binaries/mfplat-patched.dll`,
MD5 `f1602b59b7fa011bba78b38c5192b022`).

---

### 3.3 d2d1.dll Patch (Color Management)

**Symptom:** Crash mit `HResult: 0x88990028` oder
`CreateD2DDeviceResources failed`. Tritt vor allem bei Color-Proofing-Features
auf.

**Lösung:** EFFECT_REG-Eintrag in `dlls/d2d1/` für CLSID
`{1a28524c-fdd6-4aa4-ae8f-837eb8267b37}` (CLSID_D2D1ColorManagement) als
"no-op effect" (passthrough). Photoshop nutzt eigenes Color Management,
ist aber wahrscheinlich seltener betroffen als Lightroom.

---

### 3.4 Stub-DLLs (CC-Login & UI Automation)

**Symptom:** Creative-Cloud-Login hängt, oder Photoshop-Subprozesse stürzen
beim Start ab. Wine-Log zeigt fehlende Imports von:
- `NDFAPI.DLL`
- `wkscli.dll`
- `ext-ms-win-uiacore-l1-1-2.dll`

**Lösung:** mingw-w64-Stub-DLLs bauen und nach `drive_c/windows/system32/`
kopieren.

| DLL | Verhalten |
|---|---|
| `NDFAPI.DLL` | Alle Exports geben `E_NOTIMPL` zurück |
| `wkscli.dll` | Forwarder zu `netapi32.dll` (`NetWkstaGetInfo`, `NetWkstaUserGetInfo`) |
| `ext-ms-win-uiacore-l1-1-2.dll` | `UiaDisconnectAllProviders` → `S_OK` |

**Build-Integration:** In `build_appimage.sh` einen Step ergänzen, der mit
`x86_64-w64-mingw32-gcc` aus `wine-patches/stubs/sources/*.c` die DLLs
kompiliert und ins AppImage-AppDir an `usr/share/wine-stubs/` legt. Die
runtime-Fix-Funktion kopiert sie dann in den Prefix.

---

### 3.5 Creative-Cloud-Login-Probleme

**Symptom:** Anmeldung im CC Desktop App hängt oder schlägt fehl.

**Bereits gemacht:** `apply_adobe_winver_overrides()` setzt win7-Mode für
`Creative Cloud.exe`, `AdobeIPCBroker.exe`, `node.exe`, etc.

**Weitere Optionen:**
- Registry-Tweak für NLA Active Probing (Netzwerk-Erkennung):
  ```
  HKLM\SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet
  ActiveDnsProbeHost = "www.adobe.com"
  ```
- `webview2` Komponente prüfen — in [`version_configs.json`](version_configs.json)
  schon drin, sollte beim winetricks-Lauf ankommen
- WebView2 Runtime-Version: Microsoft Edge WebView2 ≥ 122 empfohlen

---

### 3.6 Neural Filters (Adobe Sensei)

**Status:** Sehr instabil unter Wine. Hängt von vkd3d-proton + DirectML-Bridge ab.

**Empfehlung:** Im GUI explizit warnen, dass Neural Filters nicht offiziell
unterstützt werden. User kann via "Switch GPU Backend" auf
`vkd3d-proton (Vulkan + OpenCL)` umschalten und es probieren.

---

## 4. Diagnose-Verbesserungen für die GUI

### 4.1 "Show Adobe Fixes Status"-Button

Read-only Variante von `apply_adobe_runtime_fixes()` — zeigt im Log:
```
GrowthSDK Files:
  ✓ Adobe Photoshop 2025/AdobeGrowthSDK.dll.disabled (disabled)
  ✗ Common Files/Adobe/.../AdobeGrowthSDK.dll (still active — needs disable)

Lowercase Symlinks:
  ✓ 47 of 47 expected symlinks present in Adobe Photoshop 2025/

DXVK Config:
  ✓ $WINEPREFIX/dxvk.conf exists with enableDummyCompositionSwapchain=True
  ✓ DXVK_CONFIG_FILE will be set at launch
```

### 4.2 Wine-Log-Analyzer

Nach Crash automatisch das letzte Wine-Log nach bekannten Mustern scannen:
- `mfplat.dll ... not found` → "Apply mfplat patch & rebuild Wine"
- `d2d1` + `0x88990028` → "Apply d2d1 ColorManagement patch"
- `SetThreadpoolTimerEx` → "Run Apply Stability Fixes" (sollte bereits laufen)
- `Library NDFAPI.DLL not found` → "Build stub DLLs"

---

## 5. Build-System Verbesserungen

### 5.1 Wine-Patch-Anwendung verifizieren

Im Build-Script nach `patch -p1` prüfen, dass **alle** `wine-patches/patches/*.patch`
sauber durchlaufen (`patch` ohne Reject-Dateien). Sonst fehlt z. B. der MSXML-Hook
in `node.c`, obwohl `embedded_xml_cdata.c` kompiliert.

Optional: `set -e` + `patch --forward` mit Abbruch bei Fehler (aktuell: Log lesen).
Nach Copy: prüfen, dass **keine** veraltete `wine-patches/dlls/msxml3/domdoc.c` mehr liegt.

### 5.2 Patched-DLL-Signaturen prüfen

Nach Wine-Build: MD5/SHA256 der gepatchten DLLs (mshtml, msxml3, ggf.
mfplat, d2d1) ins Build-Log schreiben und ggf. mit erwarteten Hashes
abgleichen.

### 5.3 Stub-DLL-Build-Step

Neuer Build-Step für die mingw-w64 Stubs (siehe 3.4), Output landet im
AppImage unter `usr/share/wine-stubs/`.

---

## 6. Dokumentation & UX

### 6.1 README erweitern

- Sektion "Bekannte Einschränkungen" mit Neural Filters, ggf. spezifischen
  Filter-Plugins
- "Wenn etwas crasht" — kurzer Triage-Guide (Log speichern, Backend
  wechseln, Deep Repair, Full Reset)

### 6.2 GUI: Erste-Hilfe-Dialog

Bei Photoshop-Exit mit Rückgabecode ≠ 0 automatisch fragen:
"Photoshop hat sich unerwartet beendet. Wine-Log analysieren?"

---

## 7. Nice-to-have

- **`.psd`-Mimetype-Association** beim Add-to-Start-Menu mit anlegen, damit
  `xdg-open file.psd` direkt Photoshop öffnet.
- **Update-Check:** Beim Start nach neuer AppImage-Version suchen
  (GitHub Releases API), nicht zwangsweise auto-installieren.
- **Backup vor riskanten Aktionen:** Vor `Full Reset` automatisch
  `~/.photoshop_cc/drive_c/users/.../AppData/Roaming/Adobe/Adobe Photoshop XXXX/Presets`
  in `~/.photoshop-backup/` sichern.

---

## 8. Quellen

- [sander110419/lightroom-cc-on-linux](https://github.com/sander110419/lightroom-cc-on-linux)
  — Hauptquelle für DLL-Patches, Stubs, Symlink-Trick
- [PhialsBasement/wine-adobe-installers](https://github.com/PhialsBasement/wine-adobe-installers)
  — bereits in [README.md](README.md) credited
- [Linux-Affinity-Installer](https://github.com/ryzendew/Linux-Affinity-Installer)
  — UI-Inspiration, ähnlicher Wine-Workflow
- Wine Staging Patchwork-Logs für mfplat / d2d1 / combase-Fixes
  zwischen 11.1 und 11.8
