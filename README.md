# Photoshop for Linux — Installer & AppImage

**Unofficial community project — v3.0**

A modern, portable AppImage that installs and runs **Adobe Photoshop** on Linux.  
Wine 11.9 is **pre-compiled and bundled** — no build tools needed on the user's system.

Inspired by the [Affinity on Linux](https://github.com/ryzendew/Linux-Affinity-Installer) project and the community work on [Photoshop-CC2022-Linux](https://github.com/LinSoftWin/Photoshop-CC2022-Linux) (LinSoftWin).

---

## ☕ Support This Project

This project is developed and maintained in my free time. If you find it useful, please consider supporting its development with a donation — it helps cover hosting, testing hardware, and the many hours of work that go into making Photoshop run smoothly on Linux.

<a href="https://ko-fi.com/3ddruck12"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support me on Ko-fi" /></a>

---

## 🚀 Features

- **Zero-compile experience** — Wine 11.9 ships pre-built inside the AppImage.
- **Modern PyQt6 GUI** — Dark theme, responsive layout, all-English interface.
- **One-Click Setup** — Creates a Wine prefix, installs winetricks components, and launches the Photoshop installer in one step.
- **Smart Wine detection** — Automatically uses the bundled Wine; falls back to a local dev build or system Wine.
- **Auto distro detection** — Installs the right packages on Debian, Arch, Fedora, and openSUSE.
- **Maintenance tools** — `winecfg`, Vulkan/OpenGL toggle, stability fixes, cache repair, prefix reset.
- **Desktop integration** — Start menu entry with **PSD file association**, `StartupWMClass` for correct taskbar grouping, and `--launch %F` to open files from the file manager.
- **Camera Raw (optional)** — One-click download and install of Adobe Camera Raw into the Wine prefix.

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

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.  
The use of **PyQt6** in this project is compliant with its GPL license.

See the [LICENSE](LICENSE) file for more details.
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

### AppImage does nothing when double-clicked (Ubuntu / Arch / CachyOS)

Many distributions need **FUSE2** for type-2 AppImages:

```bash
# Debian/Ubuntu
sudo apt install libfuse2

# Arch / CachyOS / Manjaro
sudo pacman -S fuse2
```

Then:

```bash
chmod +x Photoshop_Installer_x86_64.AppImage
./Photoshop_Installer_x86_64.AppImage
```

**Workaround without FUSE:**

```bash
./Photoshop_Installer_x86_64.AppImage --appimage-extract-and-run
```

### White bars / broken area on the Photoshop home screen

The start screen uses embedded WebView (not classic Photoshop UI).

1. **File → Open** a `.jpg` or `.psd` — if the canvas looks fine, only the home screen is affected.
2. In the installer: **Apply Adobe Runtime Fixes** (dxvk.conf) and **Apply Photoshop Stability Fixes** (disables home screen).
3. **Configure DPI Scaling** — try 96 (100%) or match your monitor (e.g. 144 for 150%).
4. **Switch GPU Backend** → try **OpenGL** if Vulkan shows glitches.
5. On **Wayland** (KDE): test an **X11** session or `export GDK_BACKEND=x11` before launch.

### Dark Mode failed during setup

Harmless — setup continues. Click **Apply Premium Dark Mode** again after setup finishes.

### Photoshop crashes on startup

1. **Apply Adobe Runtime Fixes** and **Apply Photoshop Stability Fixes**.
2. Switch GPU backend to **OpenGL** if Vulkan causes issues.
3. Use **Deep Repair** to clear cached data.
4. **Save Installation Log** — the GUI suggests fixes for known Wine error patterns.

### Installer dropdowns are empty / XML errors

This was a known issue with older Wine versions (≤ 10.0). Wine 11.9 includes native `inproc_sync` which resolves these synchronization issues. Make sure you're using the bundled Wine from this AppImage (v3.11+), not an older system Wine.

### Content-Aware / Remove Tool crashes

Wine log shows `MFCreateSampleCopierMFT` / `mfplat.dll` → see [NEXT_STEPS.md](NEXT_STEPS.md) (mfplat patch, future AppImage).

### Status shows „Photoshop: not installed“ after setup

Click **Refresh Status** in the dashboard. The app searches `Program Files`, `Program Files (x86)`, and other Adobe paths. If the Adobe installer exits with an error code but Photoshop was installed anyway, the GUI now detects `Photoshop.exe` automatically.

### Uninstall Photoshop

Use **Uninstall Photoshop** in the installer panel to remove the Photoshop folder from the Wine prefix and delete launcher entries. **Remove Start Menu Entries** only removes `.desktop` shortcuts without deleting Photoshop files.

### Open `.psd` files from the file manager

1. Run **Add to Start Menu** (registers PSD as default handler when `xdg-mime` is available).
2. Double-click a `.psd` or use **Open With → Adobe Photoshop**.

From the terminal: `./Photoshop_Installer_x86_64.AppImage --launch /path/to/file.psd`

### Camera Raw (optional)

Use **Install Camera Raw** in the installer panel, then in Photoshop: **Edit → Preferences → Camera Raw → Performance** — turn off **Use Graphics Processor**. If Camera Raw is grayed out, disable tooltips under **Edit → Preferences → Tools**.

### Known limitations

- **Neural Filters (Sensei)** — experimental; needs vkd3d-proton and often unstable under Wine.
- **Creative Cloud login** — may require WebView2 (included in One-Click Setup) and network tweaks.

---

## 🏗️ Building the AppImage

### Prerequisites

| Tool | Purpose |
|---|---|
| `gcc`, `flex`, `bison`, `make` | Compile Wine 11.9 |
| `mingw-w64` | Cross-compile Windows DLLs |
| `libx11-dev`, `libfreetype-dev`, `libgnutls28-dev`, ... | Wine build dependencies |
| `python-standalone.tar.gz` | Bundled Python runtime ([download](https://github.com/indygreg/python-build-standalone/releases)) |
| `appimagetool`, `linuxdeploy` | AppImage packaging tools (place in project root) |

### Build

```bash
# 1. Place Wine 11.9 source in wine-11.9/
# 2. Place python-standalone.tar.gz in project root
# 3. Build (compiles Wine + packages everything)
bash build_appimage.sh
```

The build script:
1. **Compiles Wine 11.9** from source with `--enable-win64 --disable-tests`
2. **Automatically applies Adobe-specific patches** from the `wine-patches/` directory (included in this repo)
3. **Bundles** the Wine runtime, standalone Python, PyQt6, and the installer script
3. **Generates** `Photoshop_Installer_x86_64.AppImage`

> **Note:** The first build takes **20–40 minutes** (Wine compilation). Subsequent builds reuse the cached Wine build and finish in under a minute.

---

## 🧪 Technical Details

| Component | Detail |
|---|---|
| **Wine** | 11.9 (vanilla + wine-patches, Adobe installer fixes) |
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
| `wine-11.9/` | Wine 11.9 source tree (used at build time only) |
| `appimagetool` | AppImage packaging tool |
| `linuxdeploy` | Library bundling tool |
| `python-standalone.tar.gz` | Standalone Python build for bundling |
| `pstux_icon.png` | Application icon |

---

## 🤝 Credits

- **[Affinity on Linux](https://github.com/ryzendew/Linux-Affinity-Installer)** — Original UI inspiration.
- **Wine Project** — The compatibility layer that makes this possible.
- **The Linux Community** — Continuous improvements to Wine, AppImage, and related tools.
- **wine-adobe-installers** PhialsBasement **(https://github.com/PhialsBasement/wine-adobe-installers)**
---

*Disclaimer: This project is not affiliated with Adobe Inc. Adobe Photoshop is a registered trademark of Adobe Inc. You must own a valid license from Adobe to use this software. This project provides only a compatibility layer (Wine) and scripts to facilitate the installation of legitimate software on Linux. It does not contain any Adobe software, cracks, or means to bypass copy protection.*
