#!/usr/bin/env python3
"""
Photoshop Linux Installer - PyQt6 GUI
Installs Adobe Photoshop on Linux via a pre-compiled Wine 11.1 build.

Copyright (C) 2026 Jens (3ddruck12)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import subprocess
import shutil
import threading
import json
import re
from pathlib import Path
import time


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def get_base_dir():
    """Return the base directory – respects AppImage mount point."""
    appdir = os.environ.get("APPDIR")
    if appdir:
        return os.path.join(appdir, "opt", "photoshop-installer")
    return os.path.dirname(os.path.abspath(__file__))


def get_wine_binary():
    """Return path to the bundled Wine binary."""
    appdir = os.environ.get("APPDIR")
    if appdir:
        wine = os.path.join(appdir, "usr", "bin", "wine")
        if os.path.isfile(wine) and os.access(wine, os.X_OK):
            return wine

    # Fallback: development / non-AppImage
    dev_wine = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "wine-11.1-build", "wine"
    )
    if os.path.isfile(dev_wine) and os.access(dev_wine, os.X_OK):
        return dev_wine

    # Last resort: system wine
    system_wine = shutil.which("wine")
    if system_wine:
        return system_wine

    return None


def get_wine_server():
    """Return path to the bundled wineserver."""
    wine = get_wine_binary()
    if wine:
        server = os.path.join(os.path.dirname(wine), "wineserver")
        if os.path.isfile(server):
            return server
    return shutil.which("wineserver")


def get_prefix_path():
    """Return the Wine prefix path."""
    return str(Path.home() / ".photoshop_cc")


def detect_pe_bitness(exe_path):
    """Detect PE executable bitness: returns 'x86', 'x64', or 'unknown'."""
    try:
        with open(exe_path, "rb") as f:
            mz = f.read(64)
            if len(mz) < 64 or mz[:2] != b"MZ":
                return "unknown"
            e_lfanew = int.from_bytes(mz[60:64], "little")
            f.seek(e_lfanew)
            pe = f.read(6)
            if len(pe) < 6 or pe[:4] != b"PE\0\0":
                return "unknown"
            f.seek(e_lfanew + 24)
            magic = int.from_bytes(f.read(2), "little")
            if magic == 0x10B:
                return "x86"
            if magic == 0x20B:
                return "x64"
    except Exception:
        return "unknown"
    return "unknown"


def wine_supports_32bit(wine_path):
    """Return True if Wine appears to have 32-bit (WoW64) support bundled.

    WoW64 builds have i386-windows/ (PE DLLs) but no i386-unix/ dir.
    Classic multilib builds have both i386-unix/ and i386-windows/.
    We check for either.
    """
    candidates = []
    appdir = os.environ.get("APPDIR")
    if appdir:
        for sub in ("i386-unix", "i386-windows"):
            candidates.extend([
                os.path.join(appdir, "usr", "lib", "wine", sub),
                os.path.join(appdir, "usr", "lib32", "wine", sub),
                os.path.join(appdir, "usr", "lib", "i386-linux-gnu", "wine", sub),
            ])
    if wine_path:
        base = os.path.abspath(os.path.join(os.path.dirname(wine_path), ".."))
        for sub in ("i386-unix", "i386-windows"):
            candidates.extend([
                os.path.join(base, "lib", "wine", sub),
                os.path.join(base, "lib32", "wine", sub),
            ])
    return any(os.path.isdir(p) for p in candidates)


def detect_distro():
    """Detect Linux distribution family for package management."""
    try:
        if os.path.exists("/etc/os-release"):
            info = {}
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        info[k] = v.strip('"')
            distro = info.get("ID", "unknown").lower()
            id_like = info.get("ID_LIKE", "").lower()

            if distro in ("ubuntu", "debian", "pop", "mint", "kali", "elementary", "zorin") or "debian" in id_like:
                return "debian"
            if distro in ("arch", "manjaro", "cachyos", "endeavouros", "garuda") or "arch" in id_like:
                return "arch"
            if distro in ("fedora", "nobara", "redhat", "centos", "rocky", "alma") or "fedora" in id_like:
                return "fedora"
            if distro in ("opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse") or "suse" in id_like:
                return "suse"
            return distro
    except Exception:
        pass
    return "unknown"


def detect_gpus():
    """Detect installed GPUs via lspci."""
    gpus = []
    try:
        result = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if any(k in line for k in ("VGA", "3D controller", "Display controller")):
                entry = {"raw": line.strip()}
                lower = line.lower()
                if "nvidia" in lower:
                    entry["vendor"] = "NVIDIA"
                elif "amd" in lower or "ati" in lower or "radeon" in lower:
                    entry["vendor"] = "AMD"
                elif "intel" in lower:
                    entry["vendor"] = "Intel"
                else:
                    entry["vendor"] = "Unknown"
                parts = line.split(": ", 1)
                entry["name"] = parts[1].strip() if len(parts) > 1 else line.strip()
                gpus.append(entry)
    except Exception:
        pass
    return gpus


# ---------------------------------------------------------------------------
# Attempt to import / install PyQt6
# ---------------------------------------------------------------------------

def ensure_pyqt6():
    """Make sure PyQt6 is importable. Return True on success."""
    try:
        import PyQt6.QtWidgets  # noqa: F401
        return True
    except ImportError:
        pass

    # Running inside AppImage → should always be bundled
    if os.environ.get("APPDIR"):
        print("FATAL: PyQt6 not found inside AppImage bundle. Rebuild required.")
        return False

    # Development mode – try pip install
    print("PyQt6 not found, attempting pip install...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--user", "PyQt6"],
            stdout=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"Failed to install PyQt6: {e}")
        print("Please install manually:")
        print("  Debian/Ubuntu:  sudo apt install python3-pyqt6 libxcb-cursor0")
        print("  Arch:           sudo pacman -S python-pyqt6")
        print("  Fedora:         sudo dnf install python3-pyqt6")
        return False


if not ensure_pyqt6():
    sys.exit(1)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QProgressBar, QScrollArea,
    QTextEdit, QGroupBox, QFileDialog, QLineEdit, QMessageBox, QMenu,
    QSlider, QDialog, QDialogButtonBox, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QDesktopServices


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------

class DependencyChecker(QThread):
    """Check for required runtime dependencies (not build deps anymore)."""
    status_signal = pyqtSignal(dict)

    def run(self):
        deps = {
            "wine (bundled)": get_wine_binary() is not None,
            "winetricks": shutil.which("winetricks") is not None,
        }
        self.status_signal.emit(deps)


class WineSetupThread(QThread):
    """Initialize Wine prefix and install winetricks components."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, prefix_path, wine_path, components):
        super().__init__()
        self.prefix_path = prefix_path
        self.wine_path = wine_path
        self.components = components

    def _make_env(self):
        env = os.environ.copy()
        env["WINEPREFIX"] = self.prefix_path
        env["WINE"] = self.wine_path

        wine_dir = os.path.dirname(self.wine_path)
        wineserver = os.path.join(wine_dir, "wineserver")
        if os.path.isfile(wineserver):
            env["WINESERVER"] = wineserver

        # Point to bundled Wine libs if inside AppImage (64-bit + 32-bit WoW64)
        appdir = os.environ.get("APPDIR")
        if appdir:
            dll_dirs = [
                os.path.join(appdir, "usr", "lib64", "wine", "x86_64-unix"),
                os.path.join(appdir, "usr", "lib", "wine", "x86_64-unix"),
                os.path.join(appdir, "usr", "lib64", "wine", "i386-unix"),
                os.path.join(appdir, "usr", "lib", "wine", "i386-unix"),
                os.path.join(appdir, "usr", "lib64", "wine"),
                os.path.join(appdir, "usr", "lib", "wine"),
            ]
            extra = ":".join(filter(os.path.isdir, dll_dirs))
            if extra:
                env["WINEDLLPATH"] = extra + ":" + env.get("WINEDLLPATH", "")

        return env

    def run(self):
        try:
            env = self._make_env()

            # Step 1 – wineboot
            self.log_signal.emit("Initializing Wine prefix...")
            self.progress_signal.emit(5)
            result = subprocess.run(
                [self.wine_path, "wineboot", "--init"],
                env=env,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
            )
            if result.returncode != 0:
                self.log_signal.emit(f"wineboot stderr: {result.stderr[:500]}")
            self.progress_signal.emit(20)

            # Step 2 – winetricks
            if self.components:
                total = len(self.components)
                for i, comp in enumerate(self.components):
                    self.log_signal.emit(f"Installing component: {comp} ({i+1}/{total})...")
                    try:
                        subprocess.run(
                            ["winetricks", "-q", comp],
                            env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=300,
                        )
                    except subprocess.TimeoutExpired:
                        self.log_signal.emit(f"Warning: {comp} timed out, continuing...")
                    pct = 20 + int((i + 1) / total * 70)
                    self.progress_signal.emit(pct)

            self.progress_signal.emit(95)
            self.log_signal.emit("Wine environment setup completed.")
            self.finished_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"Error during Wine setup: {e}")
            self.finished_signal.emit(False)


class InstallerRunnerThread(QThread):
    """Run an .exe installer inside Wine."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, wine_path, prefix_path, exe_path):
        super().__init__()
        self.wine_path = wine_path
        self.prefix_path = prefix_path
        self.exe_path = exe_path

    def run(self):
        try:
            env = os.environ.copy()
            env["WINEPREFIX"] = self.prefix_path
            self.log_signal.emit(f"Running installer: {self.exe_path}")
            bitness = detect_pe_bitness(self.exe_path)
            if bitness == "x86" and not wine_supports_32bit(self.wine_path):
                self.log_signal.emit(
                    "This installer appears to be 32-bit, but the bundled Wine build is 64-bit only."
                )
                self.log_signal.emit(
                    "Please use a 64-bit installer (e.g. Set-up.exe) or rebuild with WoW64 (32-bit) support."
                )
                self.finished_signal.emit(False)
                return
            proc = subprocess.run(
                [self.wine_path, self.exe_path],
                env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                self.log_signal.emit(f"Installer exited with code {proc.returncode}")
                if proc.stderr:
                    self.log_signal.emit(proc.stderr[:1000])
                    err_lower = proc.stderr.lower()
                    if "vulkan" in err_lower or "dri3" in err_lower:
                        self.log_signal.emit(
                            "Hint: Vulkan/DRI3 errors detected. Try switching GPU backend to OpenGL (wined3d)."
                        )
                    if "syswow64" in err_lower and "ntdll.dll" in err_lower:
                        self.log_signal.emit(
                            "Hint: Missing syswow64 indicates a 32-bit app running on 64-bit-only Wine."
                        )
                self.finished_signal.emit(False)
            else:
                self.log_signal.emit("Installer process finished.")
                self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Error running installer: {e}")
            self.finished_signal.emit(False)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class PhotoshopInstallerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photoshop for Linux")
        self.setMinimumSize(820, 620)

        icon_path = os.path.join(get_base_dir(), "pstux_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._active_thread = None
        self.init_ui()
        self.apply_theme()
        self.check_dependencies()

    # ── Theme ──────────────────────────────────────────────────────────

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
            }
            #titleLabel {
                font-size: 24px; font-weight: bold; color: #ffffff;
            }
            #menuBtn {
                font-size: 22px; background: transparent; border: none; color: #b0b0b0;
            }
            #menuBtn:hover { color: #ffffff; }
            #menuBtn::menu-indicator { image: none; }
            #statusCard {
                background-color: #252525; border: 1px solid #333;
                border-radius: 12px; padding: 15px;
            }
            QPushButton {
                background-color: #2a2a2a; color: #fff;
                border: 1px solid #444; border-radius: 8px;
                padding: 10px 20px; font-weight: 500;
            }
            QPushButton:hover { background-color: #3d3d3d; border-color: #555; }
            QPushButton#primaryBtn {
                background-color: #4caf50; border-color: #4caf50; font-weight: bold;
            }
            QPushButton#primaryBtn:hover { background-color: #45a049; }
            QPushButton#dangerBtn {
                background-color: #c62828; border-color: #c62828;
            }
            QPushButton#dangerBtn:hover { background-color: #e53935; }
            QPushButton:disabled {
                background-color: #1a1a1a; color: #555; border: 1px solid #333;
            }
            QGroupBox {
                font-weight: bold; border: 1px solid #333;
                border-radius: 8px; margin-top: 15px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #888;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                border: none; background: #1a1a1a; width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #333; min-height: 20px; border-radius: 5px;
            }
            QProgressBar {
                border: none; background-color: #1a1a1a; height: 8px;
                border-radius: 4px; text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #4ec9b0, stop:1 #5dd9c0);
                border-radius: 4px;
            }
        """)

    # ── UI Layout ──────────────────────────────────────────────────────

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(30, 20, 30, 20)
        root.setSpacing(15)

        # Header
        header = QHBoxLayout()
        logo = QLabel()
        icon_path = os.path.join(get_base_dir(), "pstux_icon.png")
        if os.path.exists(icon_path):
            logo.setPixmap(
                QPixmap(icon_path).scaled(
                    64, 64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        header.addWidget(logo)

        title = QLabel("Photoshop for Linux")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()

        donate_btn = QPushButton("\u2615 Donate")
        donate_btn.setObjectName("donateBtn")
        donate_btn.setToolTip("Support this project on Ko-fi")
        donate_btn.setStyleSheet(
            "QPushButton#donateBtn {"
            "  background-color: #ff5e5b; color: white; font-weight: bold;"
            "  border: none; border-radius: 6px; padding: 6px 14px;"
            "}"
            "QPushButton#donateBtn:hover { background-color: #ff3b37; }"
        )
        donate_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/3ddruck12"))
        )
        header.addWidget(donate_btn)

        menu_btn = QPushButton("\u2630")
        menu_btn.setFixedWidth(50)
        menu_btn.setObjectName("menuBtn")
        app_menu = QMenu(self)
        app_menu.addAction("Help", self.show_help)
        app_menu.addAction("Export Log", self.save_log)
        app_menu.addSeparator()
        app_menu.addAction("\u2615 Donate (Ko-fi)",
            lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/3ddruck12"))
        )
        app_menu.addAction("About", lambda: QMessageBox.about(
            self, "About",
            "Photoshop for Linux v3.04-alpha\n"
            "Wine 11.1 \u00b7 Pre-compiled build (WoW64)\n"
            "Community project \u2013 not affiliated with Adobe.\n\n"
            "\u2615 Support: https://ko-fi.com/3ddruck12"
        ))
        menu_btn.setMenu(app_menu)
        header.addWidget(menu_btn)
        root.addLayout(header)

        # Body split
        body = QHBoxLayout()

        # ─ LEFT: controls ─
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        ctrl_container = QWidget()
        scroll.setWidget(ctrl_container)
        ctrl = QVBoxLayout(ctrl_container)
        ctrl.setContentsMargins(0, 0, 10, 0)
        ctrl.setSpacing(10)

        # Quick Start
        qs = QGroupBox("Quick Start")
        qs_l = QVBoxLayout(qs)
        self.setup_btn = QPushButton("One-Click Setup")
        self.setup_btn.setObjectName("primaryBtn")
        self.setup_btn.setToolTip(
            "Initialize Wine prefix and install all required Windows components."
        )
        self.setup_btn.clicked.connect(self.one_click_setup)
        self.setup_btn.setEnabled(False)
        qs_l.addWidget(self.setup_btn)
        ctrl.addWidget(qs)

        # Installer & Apps
        ia = QGroupBox("Installer && Apps")
        ia_l = QVBoxLayout(ia)
        ia_l.addWidget(QLabel("Photoshop Installer (.exe):"))
        row = QHBoxLayout()
        self.exe_edit = QLineEdit()
        self.exe_edit.setPlaceholderText("No file selected...")
        self.exe_edit.setReadOnly(True)
        row.addWidget(self.exe_edit)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self.browse_installer)
        row.addWidget(browse_btn)
        ia_l.addLayout(row)

        self.run_inst_btn = QPushButton("Run Selected Installer")
        self.run_inst_btn.clicked.connect(self.run_installer)
        ia_l.addWidget(self.run_inst_btn)

        self.launch_btn = QPushButton("Launch Photoshop")
        self.launch_btn.clicked.connect(self.launch_photoshop)
        ia_l.addWidget(self.launch_btn)

        self.menu_entry_btn = QPushButton("Add to Start Menu")
        self.menu_entry_btn.clicked.connect(self.add_to_start_menu)
        ia_l.addWidget(self.menu_entry_btn)
        ctrl.addWidget(ia)

        # System Setup
        ss = QGroupBox("System Setup")
        ss_l = QVBoxLayout(ss)
        self.deps_btn = QPushButton("Install System Packages")
        self.deps_btn.setToolTip("Install winetricks and other runtime dependencies.")
        self.deps_btn.clicked.connect(self.install_missing_deps)
        ss_l.addWidget(self.deps_btn)

        self.tricks_btn = QPushButton("Install Winetricks Components")
        self.tricks_btn.setToolTip("Install Windows DLLs (msxml, vcrun, gdiplus, …).")
        self.tricks_btn.clicked.connect(self.install_winetricks_only)
        ss_l.addWidget(self.tricks_btn)
        ctrl.addWidget(ss)

        # Maintenance
        mt = QGroupBox("Maintenance / Fixes")
        mt_l = QVBoxLayout(mt)

        btn_cfg = QPushButton("Open Wine Configuration")
        btn_cfg.clicked.connect(self.open_winecfg)
        mt_l.addWidget(btn_cfg)

        btn_gpu = QPushButton("Switch GPU Backend (Vulkan / GL)")
        btn_gpu.clicked.connect(self.switch_gpu_backend)
        mt_l.addWidget(btn_gpu)

        btn_fix = QPushButton("Apply Photoshop Stability Fixes")
        btn_fix.clicked.connect(self.apply_ps_fixes)
        mt_l.addWidget(btn_fix)

        btn_repair = QPushButton("Deep Repair (Clean Caches)")
        btn_repair.clicked.connect(self.deep_repair)
        mt_l.addWidget(btn_repair)

        btn_reset = QPushButton("\u26a0 Full Environment Reset")
        btn_reset.setToolTip(
            "Kill ALL Wine processes, remove lock files, and optionally\n"
            "delete the prefix. Use after a failed/cancelled installation."
        )
        btn_reset.setStyleSheet(
            "QPushButton { background-color: #e65100; color: white; "
            "border: 1px solid #e65100; border-radius: 8px; "
            "padding: 10px 20px; font-weight: bold; }"
            "QPushButton:hover { background-color: #ff6d00; }"
        )
        btn_reset.clicked.connect(self.full_environment_reset)
        mt_l.addWidget(btn_reset)

        btn_log = QPushButton("Save Installation Log")
        btn_log.clicked.connect(self.save_log)
        mt_l.addWidget(btn_log)

        btn_nuke = QPushButton("Delete Full Wine Prefix")
        btn_nuke.setObjectName("dangerBtn")
        btn_nuke.clicked.connect(self.clean_prefix)
        mt_l.addWidget(btn_nuke)
        ctrl.addWidget(mt)

        # Advanced Settings
        adv = QGroupBox("Advanced Settings")
        adv_l = QVBoxLayout(adv)

        btn_dpi = QPushButton("Configure DPI Scaling")
        btn_dpi.setToolTip("Adjust DPI for HiDPI monitors (96\u2013480)")
        btn_dpi.clicked.connect(self.configure_dpi)
        adv_l.addWidget(btn_dpi)

        btn_gpu_info = QPushButton("Detect GPU && Recommend Settings")
        btn_gpu_info.setToolTip("Auto-detect your GPU and suggest optimal settings")
        btn_gpu_info.clicked.connect(self.detect_and_recommend_gpu)
        adv_l.addWidget(btn_gpu_info)

        ctrl.addWidget(adv)

        ctrl.addStretch()
        body.addWidget(scroll, 1)

        # ─ RIGHT: status & log ─
        right = QVBoxLayout()
        card = QFrame()
        card.setObjectName("statusCard")
        card_l = QVBoxLayout(card)

        self.dep_label = QLabel("Checking dependencies...")
        self.dep_label.setWordWrap(True)
        card_l.addWidget(self.dep_label)

        # Installation Status Dashboard
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(
            "QFrame { background-color: #2a2a2a; border: 1px solid #444; "
            "border-radius: 8px; padding: 10px; margin: 5px 0; }"
        )
        status_inner = QVBoxLayout(self.status_frame)
        status_inner.setSpacing(4)
        dash_title = QLabel("<b>\U0001f4ca Installation Status</b>")
        dash_title.setStyleSheet("border: none; color: #4ec9b0;")
        status_inner.addWidget(dash_title)
        self.status_label = QLabel("Checking...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("border: none; color: #ccc; font-size: 12px;")
        status_inner.addWidget(self.status_label)
        btn_refresh = QPushButton("\u21bb Refresh")
        btn_refresh.setFixedWidth(80)
        btn_refresh.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 3px 8px; }"
        )
        btn_refresh.clicked.connect(self._refresh_status)
        status_inner.addWidget(btn_refresh)
        card_l.addWidget(self.status_frame)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            "background-color: #1a1a1a; border: none; "
            "color: #999; font-family: monospace;"
        )
        card_l.addWidget(self.log_output)
        right.addWidget(card)

        pbar_frame = QFrame()
        pbar_l = QVBoxLayout(pbar_frame)
        pbar_top = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        pbar_top.addWidget(self.progress_label)
        pbar_top.addStretch()
        self.cancel_btn = QPushButton("\u2715 Cancel")
        self.cancel_btn.setStyleSheet(
            "QPushButton { background-color: #c62828; color: white; border: none; "
            "border-radius: 4px; padding: 4px 12px; font-size: 11px; }"
            "QPushButton:hover { background-color: #e53935; }"
        )
        self.cancel_btn.setFixedHeight(24)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.cancel_btn.hide()
        pbar_top.addWidget(self.cancel_btn)
        pbar_l.addLayout(pbar_top)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        pbar_l.addWidget(self.progress_bar)
        right.addWidget(pbar_frame)

        body.addLayout(right, 2)
        root.addLayout(body)

    # ── Helpers ────────────────────────────────────────────────────────

    def log(self, msg):
        self.log_output.append(msg)

    def log_ok(self, msg):
        self.log(f"<font color='#4caf50'>{msg}</font>")

    def log_err(self, msg):
        self.log(f"<font color='#f44336'>{msg}</font>")

    def _wine_env(self):
        env = os.environ.copy()
        env["WINEPREFIX"] = get_prefix_path()
        wine = get_wine_binary()
        if wine:
            env["WINE"] = wine
        return env

    def _set_busy(self, busy, label="Working..."):
        self.setup_btn.setEnabled(not busy)
        self.run_inst_btn.setEnabled(not busy)
        self.tricks_btn.setEnabled(not busy)
        if busy:
            self.progress_label.setText(label)
            self.cancel_btn.show()
        else:
            self.progress_label.setText("Ready")
            self.cancel_btn.hide()
            self._active_thread = None

    def _kill_all_wine_processes(self):
        """Forcefully kill ALL Wine-related processes and clean up locks."""
        killed = []

        # Step 1: graceful wineserver shutdown
        wineserver = get_wine_server()
        if wineserver:
            try:
                subprocess.run(
                    [wineserver, "-k"], timeout=5, capture_output=True
                )
                killed.append("wineserver (graceful)")
            except Exception:
                pass

        # Step 2: forcefully kill wineserver if still running
        if wineserver:
            try:
                subprocess.run(
                    [wineserver, "-k9"], timeout=5, capture_output=True
                )
            except Exception:
                pass

        # Step 3: kill all Wine-related processes by name
        wine_procs = [
            "wine", "wine64", "wine-preloader", "wine64-preloader",
            "wineserver", "wineboot", "winedbg", "winetricks",
            "msiexec.exe", "services.exe", "plugplay.exe",
            "svchost.exe", "rpcss.exe", "explorer.exe",
        ]
        for proc_name in wine_procs:
            try:
                result = subprocess.run(
                    ["pkill", "-9", "-f", proc_name],
                    capture_output=True, timeout=3,
                )
                if result.returncode == 0:
                    killed.append(proc_name)
            except Exception:
                pass

        # Step 4: clean lock files from the prefix
        prefix = Path(get_prefix_path())
        locks_cleaned = 0
        if prefix.exists():
            # Remove .lck files
            for lck in prefix.rglob("*.lck"):
                try:
                    lck.unlink()
                    locks_cleaned += 1
                except Exception:
                    pass
            # Remove wineserver socket directory
            server_dir = prefix / ".wineserver"
            if server_dir.exists():
                shutil.rmtree(server_dir, ignore_errors=True)
                locks_cleaned += 1
            # Remove /tmp wineserver sockets for this prefix
            try:
                import glob
                for sock in glob.glob("/tmp/.wine-*"):
                    if os.path.isdir(sock):
                        shutil.rmtree(sock, ignore_errors=True)
                        locks_cleaned += 1
            except Exception:
                pass

        return killed, locks_cleaned

    def _cancel_operation(self):
        """Cancel the currently running background operation."""
        if self._active_thread and self._active_thread.isRunning():
            reply = QMessageBox.question(
                self, "Cancel Operation",
                "Are you sure you want to cancel the current operation?\n\n"
                "This will:\n"
                "\u2022 Terminate the running task\n"
                "\u2022 Kill ALL Wine processes\n"
                "\u2022 Remove lock files\n\n"
                "You can use 'Full Environment Reset' afterwards if needed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.log("<font color='#ff9800'>\u26a0 Cancelling operation...</font>")

                # Terminate the thread
                self._active_thread.terminate()
                self._active_thread.wait(3000)

                # Kill all wine processes and clean locks
                killed, locks = self._kill_all_wine_processes()

                if killed:
                    self.log(f"<font color='#ff9800'>  Killed processes: {', '.join(killed)}</font>")
                if locks > 0:
                    self.log(f"<font color='#ff9800'>  Removed {locks} lock file(s)</font>")

                self._set_busy(False)
                self.progress_bar.setValue(0)
                self.log(
                    "<font color='#ff9800'>Operation cancelled. "
                    "Environment cleaned up.</font>"
                )
                self.log(
                    "<font color='#888'>Tip: Use 'Full Environment Reset' if you "
                    "still have issues, or 'One-Click Setup' to rebuild.</font>"
                )
                self._refresh_status()

    # ── Dependency check ──────────────────────────────────────────────

    def check_dependencies(self):
        self._checker = DependencyChecker()
        self._checker.status_signal.connect(self._on_deps_checked)
        self._checker.start()

    def _on_deps_checked(self, results):
        lines = ["<b>Runtime Requirements:</b><br>"]
        all_ok = True
        for name, ok in results.items():
            icon = "\u2705" if ok else "\u274c"
            lines.append(f"{icon} {name}<br>")
            if not ok:
                all_ok = False

        if all_ok:
            lines.append("<br><font color='#4caf50'>All requirements met!</font>")
            self.setup_btn.setEnabled(True)
        else:
            lines.append(
                "<br><font color='#f44336'>Some requirements are missing. "
                "Click 'Install System Packages' first.</font>"
            )
            self.setup_btn.setEnabled(False)

        self.dep_label.setText("".join(lines))
        self._refresh_status()

    def _refresh_status(self):
        """Update the installation status dashboard."""
        lines = []

        wine = get_wine_binary()
        if wine:
            try:
                result = subprocess.run(
                    [wine, "--version"], capture_output=True, text=True, timeout=5
                )
                lines.append(f"\U0001f377 Wine: {result.stdout.strip()}")
            except Exception:
                lines.append("\U0001f377 Wine: installed")
        else:
            lines.append("\U0001f377 Wine: \u274c not found")

        ps = self._find_photoshop_exe()
        if ps:
            ps_dir = os.path.basename(os.path.dirname(ps))
            lines.append(f"\U0001f3a8 Photoshop: \u2705 {ps_dir}")
        else:
            lines.append("\U0001f3a8 Photoshop: \u274c not installed")

        prefix = Path(get_prefix_path())
        if prefix.exists():
            lines.append("\U0001f4c1 Prefix: \u2705 exists")
        else:
            lines.append("\U0001f4c1 Prefix: \u274c not created")

        gpus = detect_gpus()
        if gpus:
            for gpu in gpus:
                lines.append(f"\U0001f3ae {gpu['vendor']}: {gpu['name']}")
        else:
            lines.append("\U0001f3ae GPU: not detected")

        self.status_label.setText("<br>".join(lines))

    # ── One-Click Setup ───────────────────────────────────────────────

    def one_click_setup(self):
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found! Cannot proceed.")
            return

        config = self._load_config()
        if not config:
            return

        self._set_busy(True, "Setting up Wine environment...")
        self.progress_bar.setValue(0)
        self.log("<b>Starting One-Click Setup...</b>")

        self._setup_thread = WineSetupThread(
            get_prefix_path(), wine, config.get("winetricks", [])
        )
        self._setup_thread.log_signal.connect(self.log)
        self._setup_thread.progress_signal.connect(self.progress_bar.setValue)
        self._setup_thread.finished_signal.connect(self._on_setup_finished)
        self._active_thread = self._setup_thread
        self._setup_thread.start()

    def _on_setup_finished(self, success):
        self._set_busy(False)
        if success:
            self.progress_bar.setValue(100)
            self.log_ok("<b>Setup completed!</b> You can now run the Photoshop installer.")
        else:
            self.log_err("<b>Setup failed.</b> Check the log above for details.")
        self._refresh_status()

    # ── Installer execution ───────────────────────────────────────────

    def browse_installer(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Photoshop Installer", "",
            "Executables (*.exe);;All Files (*)"
        )
        if path:
            self.exe_edit.setText(path)
            self.log(f"Selected: {path}")

    def run_installer(self):
        exe = self.exe_edit.text().strip()
        if not exe or not os.path.isfile(exe):
            self.log_err("No valid installer file selected.")
            return

        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return

        self._set_busy(True, "Running installer...")
        self._runner = InstallerRunnerThread(wine, get_prefix_path(), exe)
        self._runner.log_signal.connect(self.log)
        self._runner.finished_signal.connect(self._on_installer_finished)
        self._active_thread = self._runner
        self._runner.start()

    def _on_installer_finished(self, success):
        self._set_busy(False)
        if success:
            self.log_ok("Installer finished. Try 'Launch Photoshop'.")
        else:
            self.log_err("Installer process reported an error.")
        self._refresh_status()

    # ── Launch Photoshop ──────────────────────────────────────────────

    def _find_photoshop_exe(self):
        prefix = Path(get_prefix_path())
        candidates = [
            prefix / "drive_c" / "Program Files" / "Adobe" / "Adobe Photoshop 2025" / "Photoshop.exe",
            prefix / "drive_c" / "Program Files" / "Adobe" / "Adobe Photoshop 2024" / "Photoshop.exe",
            prefix / "drive_c" / "Program Files" / "Adobe" / "Adobe Photoshop 2021" / "Photoshop.exe",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        # Glob fallback
        for match in sorted(prefix.glob("drive_c/Program Files/Adobe/*/Photoshop.exe"), reverse=True):
            return str(match)
        return None

    def launch_photoshop(self):
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return

        ps = self._find_photoshop_exe()
        if not ps:
            self.log_err(
                "Photoshop.exe not found in prefix. "
                "Have you run the installer yet?"
            )
            return

        self.log(f"Launching Photoshop: {ps}")
        env = self._wine_env()
        try:
            subprocess.Popen(
                [wine, ps],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.log_ok("Photoshop process started.")
        except Exception as e:
            self.log_err(f"Failed to launch: {e}")

    # ── Start Menu ────────────────────────────────────────────────────

    def add_to_start_menu(self):
        try:
            home = Path.home()
            app_dir = home / ".local" / "share" / "applications"
            icon_dir = home / ".local" / "share" / "icons"
            app_dir.mkdir(parents=True, exist_ok=True)
            icon_dir.mkdir(parents=True, exist_ok=True)

            src_icon = os.path.join(get_base_dir(), "pstux_icon.png")
            dest_icon = str(icon_dir / "photoshop-linux.png")
            if os.path.isfile(src_icon):
                shutil.copy2(src_icon, dest_icon)

            appimage = os.environ.get("APPIMAGE")
            if appimage:
                exec_installer = appimage
                exec_launch = f"{appimage} --launch"
            else:
                script = os.path.abspath(__file__)
                exec_installer = f"{sys.executable} {script}"
                exec_launch = f"{sys.executable} {script} --launch"

            # Installer entry
            installer_desktop = app_dir / "photoshop-installer.desktop"
            installer_desktop.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Photoshop Installer & Maintenance\n"
                "Comment=Manage Adobe Photoshop on Linux\n"
                f"Exec={exec_installer}\n"
                f"Icon={dest_icon}\n"
                "Terminal=false\n"
                "Categories=Graphics;Settings;\n"
            )
            installer_desktop.chmod(0o644)

            # Direct launch entry (only if installed)
            ps = self._find_photoshop_exe()
            if ps:
                launch_desktop = app_dir / "photoshop-app.desktop"
                launch_desktop.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Adobe Photoshop\n"
                    "Comment=Image editing via Wine\n"
                    f"Exec={exec_launch}\n"
                    f"Icon={dest_icon}\n"
                    "Terminal=false\n"
                    "Categories=Graphics;\n"
                )
                launch_desktop.chmod(0o644)
                self.log_ok("Photoshop launcher added to start menu.")

            self.log_ok("Installer shortcut added to start menu.")
            QMessageBox.information(self, "Done", "Start menu entries created!")

        except Exception as e:
            self.log_err(f"Failed to create menu entries: {e}")

    # ── System Packages ───────────────────────────────────────────────

    def install_missing_deps(self):
        distro = detect_distro()
        self.log(f"Detected distribution family: <b>{distro}</b>")

        pkg_map = {
            "debian": "sudo apt update && sudo apt install -y winetricks libxcb-cursor0",
            "arch": "sudo pacman -S --noconfirm winetricks",
            "fedora": "sudo dnf install -y winetricks",
            "suse": "sudo zypper install -y winetricks",
        }
        cmd = pkg_map.get(distro)
        if not cmd:
            self.log_err(
                f"Unsupported distro '{distro}'. "
                "Please install 'winetricks' manually."
            )
            return

        self.log(f"Running: {cmd}")
        self._set_busy(True, "Installing packages...")

        def _worker():
            try:
                subprocess.run(cmd, shell=True, check=True)
            except Exception as e:
                print(f"Package install error: {e}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

        def _recheck():
            if t.is_alive():
                QTimer.singleShot(2000, _recheck)
            else:
                self._set_busy(False)
                self.check_dependencies()
                self.log("Dependency check refreshed.")

        QTimer.singleShot(2000, _recheck)

    # ── Winetricks only ───────────────────────────────────────────────

    def install_winetricks_only(self):
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return
        if not shutil.which("winetricks"):
            self.log_err("winetricks is not installed. Use 'Install System Packages' first.")
            return

        config = self._load_config()
        if not config:
            return

        self._set_busy(True, "Installing winetricks components...")
        self.progress_bar.setValue(0)
        self._wt_thread = WineSetupThread(
            get_prefix_path(), wine, config.get("winetricks", [])
        )
        self._wt_thread.log_signal.connect(self.log)
        self._wt_thread.progress_signal.connect(self.progress_bar.setValue)
        self._wt_thread.finished_signal.connect(self._on_setup_finished)
        self._active_thread = self._wt_thread
        self._wt_thread.start()

    # ── Wine Config ───────────────────────────────────────────────────

    def open_winecfg(self):
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return
        self.log("Opening winecfg...")
        env = self._wine_env()
        subprocess.Popen(
            [wine, "winecfg"], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    # ── DPI Scaling ───────────────────────────────────────────────────

    def configure_dpi(self):
        """Open a dialog to configure Wine DPI scaling."""
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return

        prefix = Path(get_prefix_path())
        if not prefix.exists():
            self.log_err("Wine prefix doesn't exist. Run One-Click Setup first.")
            return

        current_dpi = 96
        env = self._wine_env()
        try:
            result = subprocess.run(
                [wine, "reg", "query",
                 r"HKCU\Control Panel\Desktop", "/v", "LogPixels"],
                env=env, capture_output=True, text=True, timeout=15,
            )
            for line in result.stdout.splitlines():
                if "LogPixels" in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        current_dpi = int(parts[-1], 16)
                    break
        except Exception:
            pass

        dialog = QDialog(self)
        dialog.setWindowTitle("DPI Scaling Configuration")
        dialog.setMinimumWidth(420)
        dlg_layout = QVBoxLayout(dialog)

        info = QLabel(
            "<b>Adjust DPI for HiDPI displays</b><br>"
            "Higher values make UI elements larger in Photoshop.<br>"
            "Default: 96 DPI (100%)"
        )
        info.setWordWrap(True)
        dlg_layout.addWidget(info)

        val_label = QLabel(
            f"{current_dpi} DPI ({round(current_dpi / 96 * 100)}%)"
        )
        val_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #4ec9b0;"
        )
        val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout.addWidget(val_label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(96)
        slider.setMaximum(480)
        slider.setSingleStep(12)
        slider.setValue(current_dpi)
        slider.valueChanged.connect(
            lambda v: val_label.setText(f"{v} DPI ({round(v / 96 * 100)}%)")
        )
        dlg_layout.addWidget(slider)

        preset_row = QHBoxLayout()
        for plabel, pval in [
            ("100%", 96), ("125%", 120), ("150%", 144),
            ("200%", 192), ("300%", 288),
        ]:
            pbtn = QPushButton(plabel)
            pbtn.setFixedWidth(60)
            pbtn.clicked.connect(lambda checked, v=pval: slider.setValue(v))
            preset_row.addWidget(pbtn)
        dlg_layout.addLayout(preset_row)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        dlg_layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_dpi = slider.value()
            self.log(f"Setting DPI to {new_dpi} ({round(new_dpi / 96 * 100)}%)...")
            try:
                subprocess.run(
                    [wine, "reg", "add", r"HKCU\Control Panel\Desktop",
                     "/v", "LogPixels", "/t", "REG_DWORD",
                     "/d", str(new_dpi), "/f"],
                    env=env, capture_output=True, timeout=15,
                )
                subprocess.run(
                    [wine, "reg", "add", r"HKCU\Software\Wine\Fonts",
                     "/v", "LogPixels", "/t", "REG_DWORD",
                     "/d", str(new_dpi), "/f"],
                    env=env, capture_output=True, timeout=15,
                )
                self.log_ok(
                    f"DPI set to {new_dpi}. "
                    "Restart Photoshop for changes to take effect."
                )
                self._refresh_status()
            except Exception as e:
                self.log_err(f"Failed to set DPI: {e}")

    # ── GPU Backend ───────────────────────────────────────────────────

    def switch_gpu_backend(self):
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return

        prefix = Path(get_prefix_path())
        if not prefix.exists():
            self.log_err("Wine prefix doesn't exist. Run One-Click Setup first.")
            return

        env = self._wine_env()

        dialog = QDialog(self)
        dialog.setWindowTitle("GPU Backend & Renderer")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)

        info = QLabel(
            "<b>Choose the rendering backend:</b><br>"
            "This affects performance and feature support for Photoshop."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        group = QButtonGroup(dialog)

        rb_dxvk = QRadioButton(
            "DXVK (Vulkan) \u2014 Best performance, recommended for most GPUs"
        )
        rb_dxvk.setChecked(True)
        group.addButton(rb_dxvk)
        layout.addWidget(rb_dxvk)

        rb_vkd3d = QRadioButton(
            "vkd3d-proton (Vulkan + OpenCL) \u2014 For PS filters & Neural Filters"
        )
        group.addButton(rb_vkd3d)
        layout.addWidget(rb_vkd3d)

        rb_gl = QRadioButton(
            "OpenGL (wined3d) \u2014 Most compatible, slower"
        )
        group.addButton(rb_gl)
        layout.addWidget(rb_gl)

        rb_gdi = QRadioButton(
            "GDI (Software) \u2014 Fallback if GPU drivers have issues"
        )
        group.addButton(rb_gdi)
        layout.addWidget(rb_gdi)

        gpus = detect_gpus()
        if gpus:
            hint = "<br>".join(f"Detected: <b>{g['name']}</b>" for g in gpus)
            gpu_label = QLabel(hint)
            gpu_label.setStyleSheet("color: #4ec9b0; margin-top: 8px;")
            gpu_label.setWordWrap(True)
            layout.addWidget(gpu_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = group.checkedButton()

        if selected == rb_dxvk:
            self.log("Setting renderer to <b>Vulkan (DXVK)</b>...")
            renderer = "vulkan"
        elif selected == rb_vkd3d:
            self.log("Setting renderer to <b>Vulkan (vkd3d-proton)</b>...")
            renderer = "vulkan"
            if shutil.which("winetricks"):
                self.log("Installing vkd3d-proton via winetricks...")
                try:
                    subprocess.run(
                        ["winetricks", "-q", "vkd3d"],
                        env=env, capture_output=True, text=True, timeout=120,
                    )
                    self.log_ok("vkd3d-proton installed.")
                except subprocess.TimeoutExpired:
                    self.log_err("vkd3d-proton install timed out.")
                except Exception as e:
                    self.log_err(f"vkd3d-proton install failed: {e}")
            else:
                self.log_err(
                    "winetricks not found \u2013 cannot install vkd3d-proton. "
                    "Install winetricks first."
                )
        elif selected == rb_gl:
            self.log("Setting renderer to <b>OpenGL (wined3d)</b>...")
            renderer = "gl"
        elif selected == rb_gdi:
            self.log("Setting renderer to <b>GDI (Software)</b>...")
            renderer = "gdi"
        else:
            return

        try:
            subprocess.run(
                [wine, "reg", "add", r"HKCU\Software\Wine\Direct3D",
                 "/v", "renderer", "/t", "REG_SZ", "/d", renderer, "/f"],
                env=env, capture_output=True, timeout=15,
            )
            self.log_ok(
                "GPU backend updated. Restart Photoshop for changes to take effect."
            )
            self._refresh_status()
        except Exception as e:
            self.log_err(f"Failed to switch backend: {e}")

    # ── GPU Detection ─────────────────────────────────────────────────

    def detect_and_recommend_gpu(self):
        """Detect GPU hardware and show optimal settings recommendations."""
        gpus = detect_gpus()
        if not gpus:
            self.log_err("No GPU detected. Is 'lspci' available?")
            QMessageBox.warning(
                self, "GPU Detection",
                "No GPU could be detected.\n"
                "Make sure 'pciutils' (lspci) is installed.",
            )
            return

        msg = "<b>\U0001f3ae Detected GPUs:</b><br><br>"
        recommendations = []

        for gpu in gpus:
            vendor = gpu["vendor"]
            name = gpu["name"]
            msg += f"\u2022 <b>{name}</b><br>"

            if vendor == "NVIDIA":
                recommendations.append(
                    "<b>NVIDIA GPU:</b><br>"
                    "\u2022 Recommended: <b>DXVK</b> (Vulkan) for best performance<br>"
                    "\u2022 Use vkd3d-proton for DX12 / OpenCL (Neural Filters)<br>"
                    "\u2022 Make sure proprietary NVIDIA drivers are installed<br>"
                    "\u2022 Tip: set <code>__GL_SHADER_DISK_CACHE=1</code>"
                )
            elif vendor == "AMD":
                recommendations.append(
                    "<b>AMD GPU:</b><br>"
                    "\u2022 Recommended: <b>DXVK</b> (Vulkan) with RADV driver<br>"
                    "\u2022 vkd3d-proton works well for DX12 / OpenCL<br>"
                    "\u2022 Mesa RADV is usually pre-installed on most distros<br>"
                    "\u2022 Tip: set <code>RADV_PERFTEST=gpl</code>"
                )
            elif vendor == "Intel":
                recommendations.append(
                    "<b>Intel GPU:</b><br>"
                    "\u2022 Recommended: <b>OpenGL</b> for best compatibility<br>"
                    "\u2022 Vulkan/DXVK may work on newer Intel GPUs (Arc, Xe)<br>"
                    "\u2022 Older Intel iGPUs: stick with OpenGL (wined3d)"
                )

        if recommendations:
            msg += "<br>" + "<br><br>".join(recommendations)

        msg += (
            "<br><br><i>Use 'Switch GPU Backend' to apply "
            "the recommended renderer.</i>"
        )

        QMessageBox.information(self, "GPU Detection & Recommendations", msg)
        self.log("GPU detection completed \u2013 see recommendations dialog.")

    # ── Stability Fixes ───────────────────────────────────────────────

    def apply_ps_fixes(self):
        wine = get_wine_binary()
        if not wine:
            self.log_err("Wine binary not found!")
            return

        env = self._wine_env()
        self.log("<b>Applying Photoshop stability fixes...</b>")

        overrides = [
            ("atmlib", "native"),
            ("gdiplus", "builtin,native"),
            ("riched20", "builtin,native"),
        ]
        try:
            for dll, mode in overrides:
                self.log(f"  DLL override: {dll} → {mode}")
                subprocess.run(
                    [wine, "reg", "add",
                     r"HKCU\Software\Wine\AppDefaults\Photoshop.exe\DllOverrides",
                     "/v", dll, "/t", "REG_SZ", "/d", mode, "/f"],
                    env=env, capture_output=True, timeout=15,
                )

            self.log("  Disabling Photoshop Home Screen...")
            for ver in ("150.0", "160.0", "170.0"):
                subprocess.run(
                    [wine, "reg", "add",
                     rf"HKCU\Software\Adobe\Photoshop\{ver}",
                     "/v", "InAppMsg_CanShowHomeScreen",
                     "/t", "REG_DWORD", "/d", "0", "/f"],
                    env=env, capture_output=True, timeout=15,
                )

            self.log_ok("All stability fixes applied.")
        except Exception as e:
            self.log_err(f"Fix error: {e}")

    # ── Full Environment Reset ────────────────────────────────────────

    def full_environment_reset(self):
        """Kill all Wine processes, remove locks, optionally delete prefix."""
        msg = QMessageBox(self)
        msg.setWindowTitle("\u26a0 Full Environment Reset")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            "<b>This will forcefully reset the Wine environment:</b><br><br>"
            "\u2022 Kill ALL running Wine processes<br>"
            "\u2022 Remove all lock files and temp data<br>"
            "\u2022 Clean winetricks cache<br><br>"
            "<b>Choose an option:</b>"
        )
        btn_clean = msg.addButton(
            "Kill Processes + Clean Locks", QMessageBox.ButtonRole.AcceptRole
        )
        btn_full = msg.addButton(
            "Full Reset (+ Delete Prefix)", QMessageBox.ButtonRole.DestructiveRole
        )
        msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is None or clicked.text() == "Cancel":
            return

        delete_prefix = (clicked == btn_full)

        if delete_prefix:
            confirm = QMessageBox.warning(
                self, "Confirm Full Reset",
                "This will DELETE the entire Wine prefix!\n"
                f"{get_prefix_path()}\n\n"
                "All installed applications (Photoshop) will be lost!\n"
                "Are you absolutely sure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self.log("<b>\u26a0 Starting Full Environment Reset...</b>")

        # Step 1: Kill processes
        self.log("Step 1: Killing all Wine processes...")
        killed, locks = self._kill_all_wine_processes()
        if killed:
            self.log(f"  Killed: {', '.join(killed)}")
        else:
            self.log("  No Wine processes were running.")
        if locks > 0:
            self.log(f"  Removed {locks} lock/temp file(s).")

        # Step 2: Clean winetricks cache
        wt_cache = Path.home() / ".cache" / "winetricks"
        if wt_cache.exists():
            self.log("Step 2: Cleaning winetricks cache...")
            shutil.rmtree(wt_cache, ignore_errors=True)
            self.log("  Winetricks cache removed.")
        else:
            self.log("Step 2: No winetricks cache found.")

        # Step 3: Optionally delete prefix
        prefix = Path(get_prefix_path())
        if delete_prefix and prefix.exists():
            self.log("Step 3: Deleting Wine prefix...")
            shutil.rmtree(prefix, ignore_errors=True)
            self.log_ok(f"  Prefix deleted: {prefix}")
        elif delete_prefix:
            self.log("Step 3: Prefix doesn't exist, nothing to delete.")
        else:
            self.log("Step 3: Prefix preserved (not deleting).")

        # Step 4: Wait a moment then verify
        time.sleep(1)
        remaining = []
        for proc_name in ["wineserver", "wine", "wine64"]:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", proc_name],
                    capture_output=True, timeout=3,
                )
                if result.returncode == 0:
                    remaining.append(proc_name)
            except Exception:
                pass

        if remaining:
            self.log_err(
                f"\u26a0 Some processes still running: {', '.join(remaining)}. "
                "Try running the reset again."
            )
        else:
            self.log_ok("\u2705 Environment is clean. No Wine processes running.")

        if delete_prefix:
            self.log_ok(
                "<b>Full reset complete!</b> "
                "Use 'One-Click Setup' to rebuild from scratch."
            )
        else:
            self.log_ok(
                "<b>Process cleanup complete!</b> "
                "You can now retry your operation."
            )

        self._set_busy(False)
        self.progress_bar.setValue(0)
        self._refresh_status()

    # ── Deep Repair ───────────────────────────────────────────────────

    def deep_repair(self):
        prefix = Path(get_prefix_path())
        if not prefix.exists():
            self.log("Prefix does not exist, nothing to repair.")
            return

        reply = QMessageBox.question(
            self, "Confirm Deep Repair",
            "This will delete Adobe caches (OOBE, SLCache, SLStore).\n"
            "Photoshop itself will NOT be removed.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        user = os.environ.get("USER", "wineuser")
        targets = [
            prefix / "drive_c" / "users" / user / "AppData" / "Local" / "Adobe" / "OOBE",
            prefix / "drive_c" / "Program Files (x86)" / "Common Files" / "Adobe" / "SLCache",
            prefix / "drive_c" / "ProgramData" / "Adobe" / "SLStore",
        ]
        self.log("<b>Deep Repair – cleaning caches...</b>")
        for p in targets:
            if p.exists():
                self.log(f"  Removing: {p.name}")
                shutil.rmtree(p, ignore_errors=True)
        self.log_ok("Deep repair finished.")

    # ── Delete Prefix ─────────────────────────────────────────────────

    def clean_prefix(self):
        prefix = Path(get_prefix_path())
        if not prefix.exists():
            self.log("Prefix does not exist.")
            return

        reply = QMessageBox.warning(
            self, "Delete Wine Prefix",
            f"This will PERMANENTLY delete:\n{prefix}\n\n"
            "All installed applications and data will be lost!\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Kill wine processes first to prevent locks
        self.log("Stopping Wine processes before deletion...")
        killed, locks = self._kill_all_wine_processes()
        if killed:
            self.log(f"  Killed: {', '.join(killed)}")
        if locks > 0:
            self.log(f"  Removed {locks} lock file(s)")

        self.log(f"Deleting prefix: {prefix}")
        shutil.rmtree(prefix, ignore_errors=True)

        # Verify deletion
        if prefix.exists():
            self.log_err(
                "Could not fully delete prefix. "
                "Some files may be locked. Try 'Full Environment Reset'."
            )
        else:
            self.log_ok("Wine prefix deleted.")
        self._refresh_status()

    # ── Save Log ──────────────────────────────────────────────────────

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "photoshop_install_log.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            try:
                with open(path, "w") as f:
                    f.write(self.log_output.toPlainText())
                self.log_ok(f"Log saved: {path}")
            except Exception as e:
                self.log_err(f"Failed to save log: {e}")

    # ── Help ──────────────────────────────────────────────────────────

    def show_help(self):
        QMessageBox.information(self, "Help", (
            "<h2>Photoshop for Linux – Help</h2>"
            "<p><b>One-Click Setup:</b> Initializes Wine prefix and installs "
            "required Windows components (recommended first step).</p>"
            "<p><b>Run Selected Installer:</b> Runs the Photoshop .exe installer "
            "inside the prepared Wine environment.</p>"
            "<p><b>Launch Photoshop:</b> Starts Photoshop directly.</p>"
            "<hr>"
            "<p><b>Maintenance:</b></p>"
            "<ul>"
            "<li><i>Switch GPU Backend</i> – Vulkan (faster) or OpenGL (more compatible)</li>"
            "<li><i>Stability Fixes</i> – DLL overrides and registry tweaks</li>"
            "<li><i>Deep Repair</i> – Removes Adobe caches if login is stuck</li>"
            "<li><i>Delete Prefix</i> – Full reset (caution: all data lost)</li>"
            "</ul>"
        ))

    # ── Config loader ─────────────────────────────────────────────────

    def _load_config(self):
        try:
            cfg_path = os.path.join(get_base_dir(), "version_configs.json")
            with open(cfg_path, "r") as f:
                data = json.load(f)
            # Use the first available config
            for key in ("cc2025", "cc2021"):
                if key in data:
                    return data[key]
            self.log_err("No valid version config found.")
            return None
        except Exception as e:
            self.log_err(f"Failed to load config: {e}")
            return None


# ---------------------------------------------------------------------------
# Direct launch mode (--launch)
# ---------------------------------------------------------------------------

def direct_launch():
    """Launch Photoshop without showing the GUI."""
    wine = get_wine_binary()
    if not wine:
        print("ERROR: Wine binary not found.")
        sys.exit(1)

    prefix = Path(get_prefix_path())
    candidates = sorted(prefix.glob("drive_c/Program Files/Adobe/*/Photoshop.exe"), reverse=True)
    if not candidates:
        print("ERROR: Photoshop.exe not found in prefix.")
        print(f"Prefix: {prefix}")
        sys.exit(1)

    ps = str(candidates[0])
    print(f"Launching: {ps}")
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    os.execvpe(wine, [wine, ps], env)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--launch" in sys.argv:
        direct_launch()
        sys.exit(0)

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

    app = QApplication(sys.argv)
    window = PhotoshopInstallerGUI()
    window.show()
    sys.exit(app.exec())
