#!/bin/bash
# build_appimage.sh - Robust AppImage creation script

set -e

APP_DIR="Photoshop.AppDir"
PROJECT_DIR=$(pwd)
WINE_SOURCE="wine-adobe-installers-fix-dropdowns"

echo "Creating AppDir structure..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/usr/lib"
mkdir -p "$APP_DIR/opt/photoshop-installer"

echo "Copying project files..."
cp PhotoshopInstaller.py "$APP_DIR/opt/photoshop-installer/"
cp version_configs.json "$APP_DIR/opt/photoshop-installer/"
cp pstux_icon.png "$APP_DIR/opt/photoshop-installer/"
cp -r "$WINE_SOURCE" "$APP_DIR/opt/photoshop-installer/"

echo "Bundling Virtual Environment (venv)..."
# We copy the existing venv. Note: this is not perfectly portable but works if paths are handled.
cp -r venv "$APP_DIR/opt/photoshop-installer/"

echo "Creating AppRun..."
cat <<EOF > "$APP_DIR/AppRun"
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PATH="\$HERE/opt/photoshop-installer/venv/bin:\$PATH"
export PYTHONPATH="\$HERE/opt/photoshop-installer:\$PYTHONPATH"

# Run the installer
cd "\$HERE/opt/photoshop-installer"
./venv/bin/python3 PhotoshopInstaller.py "\$@"
EOF
chmod +x "$APP_DIR/AppRun"

echo "Creating Desktop file..."
cat <<EOF > "$APP_DIR/photoshop.desktop"
[Desktop Entry]
Type=Application
Name=Photoshop Installer for Linux
Exec=AppRun
Icon=photoshop
Categories=Graphics;
EOF

echo "Creating dummy Icon..."
cp pstux_icon.png "$APP_DIR/photoshop.png"

echo "Generating AppImage..."
export ARCH=x86_64
./appimagetool "$APP_DIR" Photoshop_Installer_x86_64.AppImage

echo "SUCCESS: Photoshop_Installer_x86_64.AppImage created!"
