# Photoshop for Linux - Installer & AppImage
**Unofficial community project**

This project provides a modern, user-friendly GUI installer and a portable AppImage to run **Adobe Photoshop CC 2021** on Linux. It uses a specially patched version of Wine to fix common installer issues like broken dropdowns and XML errors.

Inspired by the [Affinity on Linux](https://github.com/Wanaty/Affinity-Installer) project.

## 🚀 Features

- **Modern GUI**: Built with PyQt6, featuring a dark theme and intuitive layout.
- **One-Click Setup**: Automates Wine environment creation and component installation.
- **Dependency Checker**: Verifies system requirements (gcc, flex, winetricks, etc.) and offers automatic installation.
- **Maintenance Tools**: Quick access to `winecfg`, GPU backend switching (Vulkan/OpenGL), and prefix cleaning.
- **Portable AppImage**: A single executable file that bundles all necessary dependencies.
- **Stability Fixes**: Pre-configured DllOverrides and registry tweaks to disable the crash-prone Home Screen.

## 📋 Current Support

### Software
- [x] Adobe Photoshop CC 2021
- [ ] Adobe Photoshop CC 2025 (Planned)

### Linux Distributions (Auto-Detection)
- **Debian-based**: Ubuntu, Debian, Pop!_OS, Linux Mint
- **Arch-based**: Arch Linux, Manjaro
- *Other distributions require manual dependency installation.*

## 🛠️ Installation & Usage

### Option 1: Using the AppImage (Recommended)

1. Download the `Photoshop_Installer_x86_64.AppImage`.
2. Make it executable:
   ```bash
   chmod +x Photoshop_Installer_x86_64.AppImage
   ```
3. Run it:
   ```bash
   ./Photoshop_Installer_x86_64.AppImage
   ```

### Option 2: Running from Source

1. Clone the repository.
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install PyQt6
   ```
3. Run the installer:
   ```bash
   python3 PhotoshopInstaller.py
   ```

## 🕹️ Button Reference

| Section | Button | Description |
| --- | --- | --- |
| **Quick Start** | `One-Click Full Setup` | Recommended. Runs everything automatically. |
| **System Setup** | `Build Patched Wine` | Compiles Wine with Adobe fix patches. |
| | `Install System Packages` | Installs git, gcc, winetricks, etc. |
| | `Install Winetricks` | Installs MSXML, core fonts, vcruntimes. |
| **Maintenance** | `Open Winecfg` | Legacy Wine configuration tool. |
| | `Switch GPU Backend` | Toggle Vulkan (DXVK) or OpenGL. |
| | `Apply Stability Fixes` | Registry tweaks to prevent common crashes. |
| | `Deep Repair` | Cleans Adobe cache files without erasing Wine. |
| | `Save Installation Log` | Exports logs for troubleshooting. |
| | `Delete Wine Prefix` | Full reset (deletes all data). |

## 🏗️ Development & Building

To build the AppImage yourself:
1. Ensure the patched Wine source (`wine-adobe-installers-fix-dropdowns`) is in the project root.
2. Run the build script:
   ```bash
   bash build_appimage.sh
   ```

## 🧪 Technical Details

- **Wine Version**: Patched with `wine-adobe-installers-fix-dropdowns` for improved Adobe compatibility.
- **UI Framework**: PyQt6.
- **Winetricks**: Automates the installation of `msxml3`, `mshtml`, and core fonts.

## 🤝 Credits

- **Affinity Linux Team**: For the original UI inspiration.
- **PhialsBasement**: For the Wine dropdown fix patches.
- **The Linux Community**: For continuous improvements to Wine and AppImage tools.

---
*Disclaimer: This project is not affiliated with Adobe Inc. Adobe Photoshop is a registered trademark of Adobe Inc.*
