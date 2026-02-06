# Photoshop for Linux — Installer & AppImage

**Unofficial community project — v3.0**

A modern, portable AppImage that installs and runs **Adobe Photoshop** on Linux.  
Wine 11.1 is **pre-compiled and bundled** — no build tools needed on the user's system.

Inspired by the [Affinity on Linux](https://github.com/Wanaty/Affinity-Installer) project.

---

## 🚀 Features

- **Zero-compile experience** — Wine 11.1 ships pre-built inside the AppImage.
- **Modern PyQt6 GUI** — Dark theme, responsive layout, all-English interface.
- **One-Click Setup** — Creates a Wine prefix, installs winetricks components, and launches the Photoshop installer in one step.
- **Smart Wine detection** — Automatically uses the bundled Wine; falls back to a local dev build or system Wine.
- **Auto distro detection** — Installs the right packages on Debian, Arch, Fedora, and openSUSE.
- **Maintenance tools** — `winecfg`, Vulkan/OpenGL toggle, stability fixes, cache repair, prefix reset.
- **Desktop integration** — "Add to Start Menu" creates a `.desktop` entry so Photoshop appears in your application launcher.

## 📋 Supported Software

| Version | Status | Winetricks |
|---|---|---|
| Adobe Photoshop CC 2021 | ✅ Supported | msxml3, msxml6, vcrun2019, atmlib, gdiplus, corefonts |
| Adobe Photoshop CC 2025 | 🧪 Experimental | msxml3, msxml6, vcrun2022, atmlib, gdiplus, corefonts |

## 🐧 Supported Distributions (auto-detected)

| Family | Examples |
|---|---|
| **Debian-based** | Ubuntu, Debian, Pop!_OS, Linux Mint, Zorin, elementary, Kali |
| **Arch-based** | Arch Linux, Manjaro, CachyOS, EndeavourOS, Garuda |
| **Fedora-based** | Fedora, Nobara, RHEL, CentOS, Rocky, Alma |
| **openSUSE** | Tumbleweed, Leap |

Other distributions work too — you just need `wine` and `winetricks` installed manually.

---

## 🛠️ Installation & Usage

### Option 1: AppImage (Recommended)

```bash
# 1. Download the AppImage from the Releases page

# 2. Make it executable
chmod +x Photoshop_Installer_x86_64.AppImage

# 3. Ubuntu 22.04+ users: install libfuse2 first
sudo apt update && sudo apt install libfuse2

# 4. Run it
./Photoshop_Installer_x86_64.AppImage
```

The only runtime dependency is **winetricks** (used for installing Windows components like MSXML and Visual C++ runtimes). The GUI will prompt you to install it if missing.

### Option 2: Running from Source (Development)

```bash
# Clone and enter
git clone https://github.com/YOUR_USER/photoshop-appimage.git
cd photoshop-appimage

# Set up a venv
python3 -m venv venv
source venv/bin/activate
pip install PyQt6

# Run (requires wine + winetricks on PATH)
python3 PhotoshopInstaller.py
```

> **Tip:** If you're on Debian 13+ / Ubuntu 24.04+ and hit a PEP 668 error, use the system package instead:
> ```bash
> sudo apt install python3-pyqt6
> ```

---

## 🕹️ Button Reference

| Section | Button | Description |
|---|---|---|
| **Quick Start** | `One-Click Setup` | Recommended. Creates prefix, installs components, launches installer. |
| **Installer** | `Browse (...)` | Select a Photoshop `.exe` installer file. |
| | `Run Selected Installer` | Run the selected `.exe` inside the Wine prefix. |
| | `Launch Photoshop` | Start an already-installed Photoshop (auto-detects `Photoshop.exe`). |
| | `Add to Start Menu` | Creates a `.desktop` file for your application launcher. |
| **System Setup** | `Install System Packages` | Installs `winetricks` via your distro's package manager. |
| | `Install Winetricks Components` | Installs MSXML, VCRuntimes, fonts, gdiplus, atmlib. |
| **Maintenance** | `Open Wine Configuration` | Opens `winecfg` for the Photoshop prefix. |
| | `Switch GPU Backend` | Toggle between Vulkan (DXVK) and OpenGL rendering. |
| | `Apply Photoshop Stability Fixes` | Registry tweaks to disable the crash-prone Home Screen. |
| | `Deep Repair (Clean Caches)` | Removes Adobe cache files without deleting the Wine prefix. |
| | `Save Installation Log` | Exports the log window contents to a text file. |
| | `Delete Full Wine Prefix` | Nuclear option — deletes everything and starts fresh. |

---

## 🐛 Troubleshooting

### AppImage does nothing when double-clicked (Ubuntu 22.04+)

Ubuntu 22.04+ removed `libfuse2` by default. Install it:

```bash
sudo apt update && sudo apt install libfuse2
```

### "Permission denied" error

```bash
chmod +x Photoshop_Installer_x86_64.AppImage
```

### Photoshop crashes on startup

1. Click **"Apply Photoshop Stability Fixes"** in the Maintenance section.
2. Try switching the GPU backend to **OpenGL** if Vulkan causes issues.
3. Use **"Deep Repair"** to clear cached data.

### Installer dropdowns are empty / XML errors

This was a known issue with older Wine versions (≤ 10.0). Wine 11.1 includes native `inproc_sync` which resolves these synchronization issues. Make sure you're using the bundled Wine, not an older system version.

---

## 🏗️ Building the AppImage

### Prerequisites

| Tool | Purpose |
|---|---|
| `gcc`, `flex`, `bison`, `make` | Compile Wine 11.1 |
| `mingw-w64` | Cross-compile Windows DLLs |
| `libx11-dev`, `libfreetype-dev`, `libgnutls28-dev`, ... | Wine build dependencies |
| `python-standalone.tar.gz` | Bundled Python runtime ([download](https://github.com/indygreg/python-build-standalone/releases)) |
| `appimagetool`, `linuxdeploy` | AppImage packaging tools (place in project root) |

### Build

```bash
# 1. Place Wine 11.1 source in wine-11.1/
# 2. Place python-standalone.tar.gz in project root
# 3. Build (compiles Wine + packages everything)
bash build_appimage.sh
```

The build script:
1. **Compiles Wine 11.1** from source with `--enable-win64 --disable-tests` (cached after first build)
2. **Bundles** the Wine runtime, standalone Python, PyQt6, and the installer script
3. **Generates** `Photoshop_Installer_x86_64.AppImage`

> **Note:** The first build takes **20–40 minutes** (Wine compilation). Subsequent builds reuse the cached Wine build and finish in under a minute.

---

## 🧪 Technical Details

| Component | Detail |
|---|---|
| **Wine** | 11.1 (vanilla, no patches needed) |
| **Sync mechanism** | Native `inproc_sync` (replaces old esync/fsync patches) |
| **UI Framework** | PyQt6 with dark theme |
| **Wine prefix** | `~/.photoshop_cc` |
| **Winetricks** | msxml3, msxml6, vcrun2019/2022, atmlib, gdiplus, corefonts |
| **AppImage runtime** | Bundled Python + Wine + PyQt6 |

### Architecture

```
AppImage
├── usr/
│   ├── bin/         ← Wine binaries (wine, wineserver, wineboot, ...)
│   ├── lib/lib64/   ← Wine libraries + DLLs
│   ├── python/      ← Standalone Python + PyQt6
│   └── share/wine/  ← Wine data files
├── opt/photoshop-installer/
│   ├── PhotoshopInstaller.py
│   └── version_configs.json
├── AppRun           ← Entry point (sets up env vars)
└── photoshop.desktop
```

---

## 📁 Project Structure

| File | Purpose |
|---|---|
| `PhotoshopInstaller.py` | Main GUI application |
| `build_appimage.sh` | Build script (compiles Wine + creates AppImage) |
| `version_configs.json` | Photoshop version definitions + winetricks lists |
| `wine-11.1/` | Wine 11.1 source tree (used at build time only) |
| `appimagetool` | AppImage packaging tool |
| `linuxdeploy` | Library bundling tool |
| `python-standalone.tar.gz` | Standalone Python build for bundling |
| `pstux_icon.png` | Application icon |

---

## 🤝 Credits

- **[Affinity on Linux](https://github.com/Wanaty/Affinity-Installer)** — Original UI inspiration.
- **Wine Project** — The compatibility layer that makes this possible.
- **The Linux Community** — Continuous improvements to Wine, AppImage, and related tools.

---

*Disclaimer: This project is not affiliated with Adobe Inc. Adobe Photoshop is a registered trademark of Adobe Inc. You must own a valid license from Adobe to use this software. This project provides only a compatibility layer (Wine) and scripts to facilitate the installation of legitimate software on Linux. It does not contain any Adobe software, cracks, or means to bypass copy protection.*
