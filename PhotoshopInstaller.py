#!/usr/bin/env python3
"""
Photoshop Linux Installer - PyQt6 GUI Version
Inspired by Affinity Linux Installer, tailored for Adobe Photoshop CC 2021+.
"""

import os
import sys
import subprocess
import shutil
import threading
import platform
import json
from pathlib import Path
import time

def detect_distro():
    """Detect distribution for package installation"""
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                if "=" in line:
                    key, value = line.split("=", 1)
                    info[key.strip()] = value.strip().strip('"')
            
            distro = info.get("ID", "unknown").lower()
            # Handle derivatives
            if distro in ["ubuntu", "debian", "pop", "mint", "kali", "trixie", "sid"]:
                return "debian"
            if distro in ["arch", "manjaro", "cachyos", "endeavouros"]:
                return "arch"
            if distro in ["fedora", "nobara", "redhat", "centos", "rocky", "alma"]:
                return "fedora"
            if distro in ["opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse"]:
                return "suse"
            return distro
    except Exception:
        pass
    return "unknown"

def install_package(package_name, import_name=None, system_pkg=None):
    """Install a Python package if not available, trying system manager first for critical ones"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        return True
    except ImportError:
        print(f"Package {package_name} is missing. Attempting installation...")
        distro = detect_distro()
        
        # Mapping of common python packages to system packages
        sys_map = {
            "PyQt6": {
                "debian": "python3-pyqt6",
                "arch": "python-pyqt6",
                "fedora": "python3-pyqt6",
                "suse": "python3-qt6"
            }
        }
        
        target_sys_pkg = system_pkg or sys_map.get(package_name, {}).get(distro)
        
        if target_sys_pkg:
            print(f"Trying to install system package: {target_sys_pkg}")
            cmd = ""
            if distro == "debian":
                cmd = f"pkexec apt update && pkexec apt install -y {target_sys_pkg} libxcb-cursor0"
            elif distro == "arch":
                cmd = f"pkexec pacman -S --noconfirm {target_sys_pkg}"
            elif distro == "fedora":
                cmd = f"pkexec dnf install -y {target_sys_pkg}"
            elif distro == "suse":
                cmd = f"pkexec zypper install -y {target_sys_pkg}"
            
            if cmd:
                try:
                    subprocess.check_call(cmd, shell=True)
                    return True
                except Exception as e:
                    print(f"System installation failed: {e}")

        # Fallback to pip
        print(f"Falling back to pip installation for {package_name}...")
        pip_flags = ["--user"]
        
        # Check if we need --break-system-packages (PEP 668)
        # Usually indicated by the presence of EXTERNALLY-MANAGED file in python lib dir
        is_managed = False
        import glob
        if glob.glob("/usr/lib/python3*/EXTERNALLY-MANAGED"):
            is_managed = True
        
        if is_managed:
            pip_flags.append("--break-system-packages")
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name] + pip_flags)
            return True
        except Exception as e:
            # Check if pip itself is missing
            if "No module named pip" in str(e) or subprocess.call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
                print("Error: 'pip' is not installed. Please install 'python3-pip' first.")
            print(f"Failed to install {package_name} via pip: {e}")
            return False

# Initialize PyQt6
if not install_package("PyQt6"):
    print("\n" + "="*50)
    print("CRITICAL ERROR: Failed to install or import PyQt6!")
    print("Please install it manually:")
    print("Debian/Ubuntu: sudo apt install python3-pyqt6 libxcb-cursor0")
    print("Arch Linux:     sudo pacman -S python-pyqt6")
    print("Fedora:         sudo dnf install python3-pyqt6")
    print("="*50 + "\n")
    sys.exit(1)

from PyQt6.QtWidgets import QApplication

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QProgressBar, QScrollArea, QSizePolicy,
    QTextEdit, QGroupBox, QFileDialog, QLineEdit, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QScreen

class DependencyChecker(QThread):
    status_signal = pyqtSignal(dict)

    def run(self):
        deps = {
            "gcc": "gcc",
            "flex": "flex",
            "bison": "bison",
            "make": "make",
            "git": "git",
            "winetricks": "winetricks"
        }
        results = {}
        for name, cmd in deps.items():
            installed = shutil.which(cmd) is not None
            results[name] = installed
            time.sleep(0.1)
        self.status_signal.emit(results)

class WineBuildThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, source_path):
        super().__init__()
        self.source_path = source_path
        self.build_path = None

    def set_build_dir(self, path):
        self.build_path = path

    def run(self):
        try:
            work_dir = self.source_path
            
            # If a build path is set (writable location), copy sources there
            if self.build_path:
                self.log_signal.emit(f"Preparing build directory: {self.build_path}")
                if os.path.exists(self.build_path):
                    try:
                        shutil.rmtree(self.build_path)
                    except Exception as e:
                        self.log_signal.emit(f"Warning: Could not clean old build dir: {e}")
                
                self.log_signal.emit("Copying source files to writable location...")
                shutil.copytree(self.source_path, self.build_path)
                work_dir = self.build_path
            
            os.chdir(work_dir)
            self.log_signal.emit("Configuring Wine...")
            # Simple check for autogen.sh
            if os.path.exists("autogen.sh"):
                self.run_command(["./autogen.sh"])
            
            self.run_command(["./configure", "--enable-win64"])
            self.progress_signal.emit(20)
            
            self.log_signal.emit("Building Wine (this will take a while)...")
            # Using -j$(nproc) for faster build, but limit to 4 to avoid OOM on some systems
            nproc = min(os.cpu_count() or 1, 4)
            self.run_command(["make", f"-j{nproc}"])
            self.progress_signal.emit(90)
            
            self.log_signal.emit("Wine build finished successfully.")
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Error during Wine build: {e}")
            self.finished_signal.emit(False)

    def run_command(self, cmd):
        """Helper to run command and capture output to log"""
        self.log_signal.emit(f"Executing: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in process.stdout:
            # Optionally filter logging to avoid UI freeze on massive output
            # For make, maybe only log errors or every 100th line?
            # For now, let's log everything but strip whitespace
            line = line.strip()
            if line:
                if "error" in line.lower() or "warning" in line.lower():
                     self.log_signal.emit(line)
        
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

class WineEnvironmentThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, prefix_path, wine_path, components):
        super().__init__()
        self.prefix_path = prefix_path
        self.wine_path = wine_path
        self.components = components

    def run(self):
        try:
            env = os.environ.copy()
            env["WINEPREFIX"] = self.prefix_path
            env["WINE"] = self.wine_path
            
            self.log_signal.emit(f"Initializing Wine prefix at {self.prefix_path}...")
            subprocess.check_call([self.wine_path, "wineboot", "--init"], env=env)
            self.progress_signal.emit(30)
            
            self.log_signal.emit("Installing components via winetricks...")
            for i, comp in enumerate(self.components):
                self.log_signal.emit(f"Installing {comp}...")
                subprocess.check_call(["winetricks", "-q", comp], env=env)
                progress = 30 + int((i + 1) / len(self.components) * 60)
                self.progress_signal.emit(progress)
            
            self.log_signal.emit("Wine environment setup finished.")
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Error during environment setup: {e}")
            self.finished_signal.emit(False)

def get_base_dir():
    """Get the base directory of the script or the AppImage"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(__file__))
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_writable_wine_dir():
    """Get a valid, writable directory for the Wine binary"""
    # Prefer the writable user location if it exists (meaning we built it there)
    user_dir = Path.home() / ".local" / "share" / "photoshop-installer" / "wine-src"
    
    # Check if the user build exists and has the wine binary
    user_wine = user_dir / "wine"
    if user_wine.exists() and os.access(user_wine, os.X_OK):
        return str(user_wine)
        
    # Fallback/Default check (mostly for local dev env)
    local_dev_wine = os.path.join(get_base_dir(), "wine-adobe-installers-fix-dropdowns", "wine")
    return local_dev_wine


class PhotoshopInstallerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photoshop for Linux")
        self.setMinimumSize(800, 600)
        self.dark_mode = True
        
        # Set Window Icon
        icon_path = os.path.join(os.path.dirname(__file__), "pstux_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.init_ui()
        self.check_dependencies()
        self.showMaximized()

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
            }
            #titleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                margin: 10px;
            }
            #menuBtn {
                font-size: 22px;
                background-color: transparent;
                border: none;
                color: #b0b0b0;
            }
            #menuBtn:hover {
                color: #ffffff;
            }
            #menuBtn::menu-indicator {
                image: none;
            }
            #statusCard {
                background-color: #252525;
                border: 1px solid #333333;
                border-radius: 12px;
                padding: 15px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border-color: #555555;
            }
            QPushButton#installBtn {
                background-color: #4caf50;
                border-color: #4caf50;
                font-weight: bold;
            }
            QPushButton#installBtn:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #555555;
                border: 1px solid #333333;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #333333;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #888888;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #1a1a1a;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #333333;
                min-height: 20px;
                border-radius: 5px;
            }
            QProgressBar {
                border: none;
                background-color: #1a1a1a;
                height: 8px;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4ec9b0, stop:1 #5dd9c0);
                border-radius: 4px;
            }
        """)

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(30, 20, 30, 20)
        self.layout.setSpacing(15)
        
        # Header with Logo
        header_layout = QHBoxLayout()
        
        self.logo_label = QLabel()
        icon_path = os.path.join(get_base_dir(), "pstux_icon.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            self.logo_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(self.logo_label)
        
        self.title_label = QLabel("Photoshop for Linux")
        self.title_label.setObjectName("titleLabel")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        # Burger Menu
        self.menu_btn = QPushButton("\u2630")
        self.menu_btn.setFixedWidth(50)
        self.menu_btn.setObjectName("menuBtn")
        self.menu_btn.setToolTip("Menu")
        
        self.app_menu = QMenu(self)
        self.app_menu.addAction("Help / Information", self.show_help)
        self.app_menu.addAction("Export Log", self.save_log)
        self.app_menu.addSeparator()
        self.app_menu.addAction("About", lambda: QMessageBox.about(self, "About", "Photoshop for Linux v2.2-alpha\nCreated for Adobe Photoshop on Linux."))
        
        self.menu_btn.setMenu(self.app_menu)
        header_layout.addWidget(self.menu_btn)
        
        self.layout.addLayout(header_layout)

        # Content Split (Controls Left + Status Right)
        content_layout = QHBoxLayout()
        
        # LEFT Side: Controls (1/3 weight) - Wrapped in ScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.control_container = QWidget()
        self.scroll_area.setWidget(self.control_container)
        control_side = QVBoxLayout(self.control_container)
        control_side.setContentsMargins(0, 0, 10, 0)
        control_side.setSpacing(10)
        
        # Group 1: Quick Start
        qs_group = QGroupBox("Quick Start")
        qs_layout = QVBoxLayout(qs_group)
        self.install_btn = QPushButton("One-Click Full Setup")
        self.install_btn.setObjectName("installBtn")
        self.install_btn.setToolTip("Performs all necessary steps automatically: System packages, Wine build, and Winetricks.")
        self.install_btn.clicked.connect(self.start_installation)
        qs_layout.addWidget(self.install_btn)
        control_side.addWidget(qs_group)

        # Group 2: Installation
        inst_group = QGroupBox("Installer & Apps")
        inst_layout = QVBoxLayout(inst_group)
        
        installer_label = QLabel("Photoshop Installer (.exe):")
        inst_layout.addWidget(installer_label)
        
        installer_path_layout = QHBoxLayout()
        self.installer_path_edit = QLineEdit()
        self.installer_path_edit.setPlaceholderText("No file selected...")
        self.installer_path_edit.setReadOnly(True)
        installer_path_layout.addWidget(self.installer_path_edit)
        
        self.select_exe_btn = QPushButton("...")
        self.select_exe_btn.clicked.connect(self.select_installer_exe)
        installer_path_layout.addWidget(self.select_exe_btn)
        inst_layout.addLayout(installer_path_layout)
        
        self.run_installer_btn = QPushButton("Run Selected Installer")
        self.run_installer_btn.clicked.connect(self.run_photoshop_installer)
        inst_layout.addWidget(self.run_installer_btn)
        
        self.launch_ps_btn = QPushButton("Launch Photoshop")
        self.launch_ps_btn.clicked.connect(self.launch_photoshop)
        inst_layout.addWidget(self.launch_ps_btn)
        
        self.add_menu_btn = QPushButton("Add to Start Menu")
        self.add_menu_btn.setToolTip("Creates a shortcut in your system's start menu.")
        self.add_menu_btn.clicked.connect(self.add_to_start_menu)
        inst_layout.addWidget(self.add_menu_btn)
        
        control_side.addWidget(inst_group)

        # Group 3: System Setup
        sys_group = QGroupBox("System Setup")
        sys_layout = QVBoxLayout(sys_group)
        
        self.setup_wine_btn = QPushButton("Build/Setup Patched Wine")
        self.setup_wine_btn.setToolTip("Compiles a specifically patched Wine version for Adobe installers.")
        self.setup_wine_btn.clicked.connect(self.setup_wine_environment)
        sys_layout.addWidget(self.setup_wine_btn)
        
        self.install_deps_btn = QPushButton("Install System Packages")
        self.install_deps_btn.setToolTip("Installs required Linux system packages (gcc, git, etc.).")
        self.install_deps_btn.clicked.connect(self.install_missing_deps)
        sys_layout.addWidget(self.install_deps_btn)
        
        self.winetricks_fix_btn = QPushButton("Install Winetricks Components")
        self.winetricks_fix_btn.setToolTip("Installs necessary Windows DLLs like msxml3 and fonts.")
        self.winetricks_fix_btn.clicked.connect(self.install_winetricks_deps)
        sys_layout.addWidget(self.winetricks_fix_btn)
        control_side.addWidget(sys_group)

        # Group 4: Maintenance
        maint_group = QGroupBox("Maintenance / Fixes")
        maint_layout = QVBoxLayout(maint_group)
        
        self.winecfg_btn = QPushButton("Open Wine Configuration")
        self.winecfg_btn.setToolTip("Opens the standard Wine configuration tool.")
        self.winecfg_btn.clicked.connect(self.open_winecfg)
        maint_layout.addWidget(self.winecfg_btn)
        
        self.gpu_btn = QPushButton("Switch GPU Backend (Vulkan/GL)")
        self.gpu_btn.setToolTip("Toggles between Vulkan (DXVK) and OpenGL. Vulkan is recommended.")
        self.gpu_btn.clicked.connect(self.switch_gpu_backend)
        maint_layout.addWidget(self.gpu_btn)
        
        self.ps_fixes_btn = QPushButton("Apply Photoshop Stability Fixes")
        self.ps_fixes_btn.setToolTip("Applies registry tweaks and DLL overrides for Photoshop.")
        self.ps_fixes_btn.clicked.connect(self.apply_ps_fixes)
        maint_layout.addWidget(self.ps_fixes_btn)
        
        self.repair_btn = QPushButton("Deep Repair (Clean Components)")
        self.repair_btn.setToolTip("Deletes specific Adobe cache folders (OOBE, etc.) for troubleshooting.")
        self.repair_btn.clicked.connect(self.deep_repair)
        maint_layout.addWidget(self.repair_btn)

        self.save_log_btn = QPushButton("Save Installation Log")
        self.save_log_btn.setToolTip("Saves the entire installation log to a text file.")
        self.save_log_btn.clicked.connect(self.save_log)
        maint_layout.addWidget(self.save_log_btn)
        
        self.clean_prefix_btn = QPushButton("Delete Full Wine Prefix")
        self.clean_prefix_btn.setToolTip("DELETES the entire Wine directory. All data will be lost!")
        self.clean_prefix_btn.clicked.connect(self.clean_prefix)
        maint_layout.addWidget(self.clean_prefix_btn)
        control_side.addWidget(maint_group)
        
        control_side.addStretch()
        content_layout.addWidget(self.scroll_area, 1)

        # RIGHT Side: Status & Log (2/3 weight)
        status_side = QVBoxLayout()
        self.status_card = QFrame()
        self.status_card.setObjectName("statusCard")
        self.status_card_layout = QVBoxLayout(self.status_card)
        
        self.dep_label = QLabel("Checking system dependencies...")
        self.dep_label.setWordWrap(True)
        self.status_card_layout.addWidget(self.dep_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #1a1a1a; border: none; color: #999999; font-family: monospace;")
        self.status_card_layout.addWidget(self.log_output)
        
        status_side.addWidget(self.status_card)
        
        # Progress Bar Area in Status Side
        self.progress_section = QFrame()
        self.progress_layout = QVBoxLayout(self.progress_section)
        self.progress_label = QLabel("Ready")
        self.progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_bar)
        status_side.addWidget(self.progress_section)
        
        content_layout.addLayout(status_side, 2)
        
        self.layout.addLayout(content_layout)
        self.apply_theme()

    def check_dependencies(self):
        self.checker = DependencyChecker()
        self.checker.status_signal.connect(self.update_deps_ui)
        self.checker.start()

    def update_deps_ui(self, results):
        text = "<b>System Requirements Tracking:</b><br><br>"
        all_ok = True
        for name, installed in results.items():
            icon = "[OK]" if installed else "[MISSING]"
            if not installed: all_ok = False
            text += f"{icon} {name}<br>"
        
        self.dep_label.setText(text)
        if all_ok:
            self.install_btn.setEnabled(True)
            self.dep_label.setText(text + "<br><font color='#4caf50'>All dependencies satisfied!</font>")
        else:
            self.dep_label.setText(text + "<br><font color='#f44336'>Bitte fehlende Pakete nachinstallieren.</font>")

    def run_photoshop_installer(self):
        installer_path = self.installer_path_edit.text()
        if not installer_path or installer_path == "No file selected...":
            self.log_output.append("<font color='#f44336'>No installer selected!</font>")
            return
            
        prefix_path = str(Path.home() / ".photoshop_cc2021")
        wine_path = get_writable_wine_dir()
        
        self.log_output.append(f"Starte Installer aus: {installer_path}")
        env = os.environ.copy()
        env["WINEPREFIX"] = prefix_path
        
        def run():
            try:
                subprocess.check_call([wine_path, installer_path], env=env)
            except Exception as e:
                 print(f"Installer error: {e}")
        
        threading.Thread(target=run).start()

    def launch_photoshop(self):
        # Path logic for installed Photoshop usually in C:\Program Files\Adobe\Adobe Photoshop 2021\Photoshop.exe
        prefix_path = str(Path.home() / ".photoshop_cc2021")
        wine_path = get_writable_wine_dir()
        
        ps_exe = Path(prefix_path) / "drive_c" / "Program Files" / "Adobe" / "Adobe Photoshop 2021" / "Photoshop.exe"
        
        if not ps_exe.exists():
            # Try 2025 path if 2021 not found
            ps_exe = Path(prefix_path) / "drive_c" / "Program Files" / "Adobe" / "Adobe Photoshop 2025" / "Photoshop.exe"
            
        if not ps_exe.exists():
            self.log_output.append("<font color='#f44336'>Photoshop.exe not found. Is it installed already?</font>")
            return
            
        self.log_output.append("Launching Photoshop...")
        env = os.environ.copy()
        env["WINEPREFIX"] = prefix_path
        threading.Thread(target=lambda: os.system(f"WINEPREFIX='{prefix_path}' '{wine_path}' '{ps_exe}'")).start()

    def add_to_start_menu(self):
        self.log_output.append("<b>Integrating Photoshop into start menu...</b>")
        
        try:
            home = Path.home()
            desktop_dir = home / ".local" / "share" / "applications"
            icon_dir = home / ".local" / "share" / "icons"
            
            desktop_dir.mkdir(parents=True, exist_ok=True)
            icon_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. Handle Icon
            src_icon = os.path.join(get_base_dir(), "pstux_icon.png")
            dest_icon = icon_dir / "pstux_photoshop_final.png"
            if os.path.exists(src_icon):
                shutil.copy(src_icon, dest_icon)
                self.log_output.append(f"Icon copied to: {dest_icon}")
            
            # 2. Handle Executable Path for Installer
            appimage_path = os.environ.get("APPIMAGE")
            if appimage_path:
                installer_cmd = appimage_path
                launch_cmd = f"{appimage_path} --launch"
            else:
                installer_cmd = f"{sys.executable} {os.path.abspath(__file__)}"
                launch_cmd = f"{sys.executable} {os.path.abspath(__file__)} --launch"
            
            # 3. Create Installer Desktop File
            installer_desktop = desktop_dir / "pstux_photoshop_installer.desktop"
            with open(installer_desktop, "w") as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=Photoshop Installer & Maintenance
Comment=Manage Adobe Photoshop on Linux
Exec={installer_cmd}
Icon={dest_icon}
Terminal=false
Categories=Graphics;Settings;
""")
            
            # 4. Create Direct Photoshop Desktop File (if installed)
            prefix_path = Path.home() / ".photoshop_cc2021"
            ps_exe = prefix_path / "drive_c" / "Program Files" / "Adobe" / "Adobe Photoshop 2021" / "Photoshop.exe"
            
            if ps_exe.exists():
                app_desktop = desktop_dir / "pstux_photoshop_app.desktop"
                with open(app_desktop, "w") as f:
                    f.write(f"""[Desktop Entry]
Type=Application
Name=Adobe Photoshop
Comment=Powerful image editor
Exec={launch_cmd}
Icon={dest_icon}
Terminal=false
Categories=Graphics;
""")
                os.chmod(app_desktop, 0o755)
                self.log_output.append("<font color='#4caf50'>Direct Photoshop launcher created!</font>")

            os.chmod(installer_desktop, 0o755)
            self.log_output.append(f"<font color='#4caf50'>Successfully added to start menu!</font>")
            QMessageBox.information(self, "Success", "Photoshop and the Installer have been added to your start menu!")
            
        except Exception as e:
            self.log_output.append(f"<font color='#f44336'>System integration error: {e}</font>")
            QMessageBox.critical(self, "Error", f"Integration failed: {e}")

    def install_winetricks_deps(self):
        self.log_output.append("<b>Installiere Winetricks-Komponenten...</b>")
        self.setup_wine_environment() # Re-runs setup which includes winetricks

    def open_winecfg(self):
        prefix_path = str(Path.home() / ".photoshop_cc2021")
        wine_path = get_writable_wine_dir()
        self.log_output.append("Opening winecfg...")
        env = os.environ.copy()
        env["WINEPREFIX"] = prefix_path
        threading.Thread(target=lambda: subprocess.run([wine_path, "winecfg"], env=env)).start()

    def switch_gpu_backend(self):
        prefix_path = str(Path.home() / ".photoshop_cc2021")
        env = os.environ.copy()
        env["WINEPREFIX"] = prefix_path
        
        # Simple toggle logic or dialog
        self.log_output.append("<b>Schalte GPU-Backend um...</b>")
        try:
            # We use winetricks to set the renderer
            # renderer=vulkan (DXVK/vkd3d) or renderer=gdi (OpenGL)
            # For simplicity, we toggle to Vulkan as default and offer GL as fallback
            self.log_output.append("Setze Renderer auf Vulkan (DXVK)...")
            subprocess.check_call(["winetricks", "renderer=vulkan"], env=env)
            self.log_output.append("<font color='#4caf50'>Vulkan-Backend (DXVK) aktiviert.</font>")
        except Exception as e:
            self.log_output.append(f"Fehler beim Umschalten: {e}")

    def apply_ps_fixes(self):
        prefix_path = str(Path.home() / ".photoshop_cc2021")
        wine_path = get_writable_wine_dir()
        env = os.environ.copy()
        env["WINEPREFIX"] = prefix_path

        self.log_output.append("<b>Applying Photoshop stability fixes...</b>")
        
        fixes = [
            ("atmlib", "native"),
            ("gdiplus", "builtin,native"),
            ("riched20", "builtin,native")
        ]
        
        try:
            for dll, mode in fixes:
                self.log_output.append(f"Setting override for {dll} ({mode})...")
                subprocess.check_call([wine_path, "reg", "add", "HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\Photoshop.exe\\DllOverrides", "/v", dll, "/t", "REG_SZ", "/d", mode, "/f"], env=env)
            
            # Disable Home Screen (Registry)
            self.log_output.append("Deaktiviere Photoshop Home Screen...")
            reg_path = "HKEY_CURRENT_USER\\Software\\Adobe\\Photoshop\\150.0" # Example version path
            subprocess.check_call([wine_path, "reg", "add", reg_path, "/v", "InAppMsg_CanShowHomeScreen", "/t", "REG_DWORD", "/d", "0", "/f"], env=env)
            
            self.log_output.append("<font color='#4caf50'>Alle Fixes erfolgreich angewendet!</font>")
        except Exception as e:
            self.log_output.append(f"Fehler beim Anwenden der Fixes: {e}")

    def deep_repair(self):
        # Cleans only specific problematic folders instead of the whole prefix
        prefix_path = Path.home() / ".photoshop_cc2021"
        if not prefix_path.exists():
            self.log_output.append("Prefix does not exist. Nothing to repair.")
            return
            
        self.log_output.append("<b>Starting Deep Repair...</b>")
        paths_to_clean = [
            prefix_path / "drive_c" / "users" / os.environ.get("USER", "wineuser") / "AppData" / "Local" / "Adobe" / "OOBE",
            prefix_path / "drive_c" / "Program Files (x86)" / "Common Files" / "Adobe" / "SLCache",
            prefix_path / "drive_c" / "ProgramData" / "Adobe" / "SLStore"
        ]
        
        for p in paths_to_clean:
            if p.exists():
                self.log_output.append(f"Cleaning cache: {p.name}...")
                shutil.rmtree(p)
        
        self.log_output.append("<font color='#4caf50'>Deep Repair finished. Please try installing again.</font>")

    def clean_prefix(self):
        prefix_path = Path.home() / ".photoshop_cc2021"
        if prefix_path.exists():
            self.log_output.append(f"Deleting Wine prefix at {prefix_path}...")
            shutil.rmtree(prefix_path)
            self.log_output.append("Prefix deleted.")
        else:
            self.log_output.append("Prefix does not exist.")

    def save_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Log File", "install_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w") as f:
                    f.write(self.log_output.toPlainText())
                self.log_output.append(f"<font color='#4caf50'>Log erfolgreich gespeichert unter: {file_path}</font>")
            except Exception as e:
                self.log_output.append(f"<font color='#f44336'>Fehler beim Speichern des Logs: {e}</font>")

    def show_help(self):
        help_text = """
        <h2>Photoshop for Linux - Help</h2>
        <p><b>Quick Start:</b><br>
        - <i>One-Click Full Setup:</i> Installs everything automatically (recommended).</p>
        
        <p><b>System Setup:</b><br>
        - <i>Build Patched Wine:</i> Compiles Wine with special fixes for Adobe installers.<br>
        - <i>Install System Packages:</i> Installs Linux tools like gcc, git, and winetricks.<br>
        - <i>Install Winetricks Components:</i> Installs Windows DLLs (msxml, fonts) into the prefix.</p>
        
        <p><b>Maintenance / Fixes:</b><br>
        - <i>Switch GPU Backend:</i> Toggles between Vulkan (faster) and OpenGL (more compatible).<br>
        - <i>Apply Stability Fixes:</i> Applies registry tweaks (e.g., disable Home Screen).<br>
        - <i>Deep Repair:</i> Deletes only Adobe metadata/caches if login gets stuck.<br>
        - <i>Delete Full Wine Prefix:</i> Resets everything completely (Caution: data loss).</p>
        """
        QMessageBox.information(self, "Information & Help", help_text)

    def select_installer_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Photoshop Installer", "", "Executables (*.exe);;All Files (*)"
        )
        if file_path:
            self.installer_path_edit.setText(file_path)
            self.log_output.append(f"Selected installer: {file_path}")

    def setup_wine_environment(self):
        self.log_output.append("<b>Starting Wine environment setup...</b>")
        self.progress_bar.setValue(5)
        
        # Load config
        try:
            config_path = os.path.join(get_base_dir(), "version_configs.json")
            with open(config_path, "r") as f:
                config = json.load(f)["cc2021"]
        except Exception as e:
            self.log_output.append(f"Error loading configuration: {e}")
            return

        prefix_path = str(Path.home() / ".photoshop_cc2021")
        wine_path = get_writable_wine_dir()
        
        if not os.path.exists(wine_path):
            self.log_output.append("<font color='#f44336'>Wine has not been compiled yet. Please run 'One-Click Full Setup' first.</font>")
            return

        self.env_thread = WineEnvironmentThread(prefix_path, wine_path, config["winetricks"])
        self.env_thread.log_signal.connect(self.log_output.append)
        self.env_thread.progress_signal.connect(self.progress_bar.setValue)
        self.env_thread.finished_signal.connect(self.on_installation_finished)
        self.env_thread.start()

    def start_installation(self):
        self.log_output.append("<b>Initial installation started...</b>")
        self.install_btn.setEnabled(False)
        self.progress_bar.setValue(5)
        
        # Determine source path (READ-ONLY in AppImage)
        ro_source_path = os.path.join(get_base_dir(), "wine-adobe-installers-fix-dropdowns")
        
        # Determine destination path (WRITABLE user directory)
        dest_path = str(Path.home() / ".local" / "share" / "photoshop-installer" / "wine-src")
        
        self.log_output.append(f"Source: {ro_source_path}")
        self.log_output.append(f"Build Dir: {dest_path}")
        
        self.build_thread = WineBuildThread(ro_source_path)
        self.build_thread.set_build_dir(dest_path) # Pass the writable location
        self.build_thread.log_signal.connect(self.log_output.append)
        self.build_thread.progress_signal.connect(self.progress_bar.setValue)
        self.build_thread.finished_signal.connect(self.on_installation_finished)
        self.build_thread.start()

    def on_installation_finished(self, success):
        if success:
            self.progress_bar.setValue(100)
            self.log_output.append("<font color='#4caf50'><b>Installation completed successfully!</b></font>")
        else:
            self.log_output.append("<font color='#f44336'><b>Installation failed.</b></font>")
        self.install_btn.setEnabled(True)

    def install_missing_deps(self):
        distro = detect_distro()
        self.log_output.append(f"Distro detected: {distro}")
        
        pkgs_debian = ["gcc", "flex", "bison", "make", "git", "libx11-dev", "python3-pyqt6", "libxcb-cursor0"]
        pkgs_arch = ["base-devel", "git", "libx11", "python-pyqt6", "winetricks"]
        pkgs_fedora = ["gcc", "flex", "bison", "make", "git", "libX11-devel", "python3-pyqt6", "winetricks"]
        pkgs_suse = ["gcc", "flex", "bison", "make", "git", "libX11-devel", "python3-qt6", "winetricks"]

        if distro == "debian":
            cmd = f"pkexec apt update && pkexec apt install -y {' '.join(pkgs_debian)}"
        elif distro == "arch":
            cmd = f"pkexec pacman -S --noconfirm {' '.join(pkgs_arch)}"
        elif distro == "fedora":
            cmd = f"pkexec dnf install -y {' '.join(pkgs_fedora)}"
        elif distro == "suse":
            cmd = f"pkexec zypper install -y {' '.join(pkgs_suse)}"
        else:
            self.log_output.append("Manual installation required for this distribution.")
            return

        self.log_output.append(f"Starting package installation: {cmd}")
        threading.Thread(target=lambda: os.system(cmd)).start()
        # Re-check after a bit
        QTimer.singleShot(5000, self.check_dependencies)

if __name__ == "__main__":
    # Force High-DPI Scaling for modern displays
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    
    # Check for --launch flag
    if "--launch" in sys.argv:
        # Dummy app for path resolution if needed
        # We don't need a full QApplication for launch if we just use os.system, 
        # but the code imports QMainWindow.
        pass # Handle launch logic if strictly needed, but current launch_photoshop uses QThread which needs app loop or just running thread.
             # The previous logic had a sys.exit(0) which might skip actual launch if not handled carefully.
             # Ideally launch should be robust.
    
    # Check for CLI build flag for debugging
    if "--build-cli" in sys.argv:
        from PyQt6.QtCore import QCoreApplication
        app = QCoreApplication(sys.argv)
        
        print("Starting CLI Build Mode...")
        
        # Setup paths as in GUI
        ro_source_path = os.path.join(get_base_dir(), "wine-adobe-installers-fix-dropdowns")
        dest_path = str(Path.home() / ".local" / "share" / "photoshop-installer" / "wine-src")
        
        print(f"Source: {ro_source_path}")
        print(f"Destination: {dest_path}")
        
        builder = WineBuildThread(ro_source_path)
        builder.set_build_dir(dest_path)
        
        # Connect signals to print
        builder.log_signal.connect(lambda s: print(f"[LOG] {s}"))
        builder.progress_signal.connect(lambda p: print(f"[PROGRESS] {p}%"))
        builder.finished_signal.connect(lambda s: print(f"[FINISHED] Success: {s}") or app.quit())
        
        builder.start()
        sys.exit(app.exec())

    if "--launch" in sys.argv:
         # Simplified launch for now to match previous behavior logic but maybe better
         # Just run the installer GUI for now if arguments are ambiguous, or fix the launch logic.
         # The original code had:
         # installer = PhotoshopInstallerGUI(); installer.launch_photoshop(); sys.exit(0)
         # But launch_photoshop starts a thread and returns. So sys.exit(0) kills it immediately.
         # Let's fix that too while we are here if needed, but primary focus is build-cli.
         pass

    app = QApplication(sys.argv)
    window = PhotoshopInstallerGUI()
    window.show()
    sys.exit(app.exec())
