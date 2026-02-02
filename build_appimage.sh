#!/bin/bash
# build_appimage.sh - Professional AppImage creation with linuxdeploy

set -e

APP_DIR="Photoshop.AppDir"
PROJECT_DIR=$(pwd)
WINE_SOURCE="wine-adobe-installers-fix-dropdowns"

echo "Cleanup old AppDir..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr/bin"
mkdir -p "$APP_DIR/opt/photoshop-installer"

echo "Copying project files..."
cp PhotoshopInstaller.py "$APP_DIR/opt/photoshop-installer/"
cp version_configs.json "$APP_DIR/opt/photoshop-installer/"
cp pstux_icon.png "$APP_DIR/opt/photoshop-installer/"
cp -r "$WINE_SOURCE" "$APP_DIR/opt/photoshop-installer/"

echo "Bundling Virtual Environment..."
# Ensure PyQt6 is in the host venv so linuxdeploy can find its libs
source venv/bin/activate
pip install PyQt6 --quiet

# Copy venv to AppDir
cp -r venv "$APP_DIR/opt/photoshop-installer/"

echo "Creating AppRun..."
cat <<EOF > "$APP_DIR/AppRun"
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PATH="\$HERE/opt/photoshop-installer/venv/bin:\$PATH"
export PYTHONPATH="\$HERE/opt/photoshop-installer:\$PYTHONPATH"
export LD_LIBRARY_PATH="\$HERE/usr/lib:\$HERE/opt/photoshop-installer/venv/lib/python3.12/site-packages/PyQt6/Qt6/lib:\$LD_LIBRARY_PATH"
export QT_PLUGIN_PATH="\$HERE/opt/photoshop-installer/venv/lib/python3.12/site-packages/PyQt6/Qt6/plugins"

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

cp pstux_icon.png "$APP_DIR/photoshop.png"
# linuxdeploy requires standard resolutions
mogrify -resize 512x512 "$APP_DIR/photoshop.png" || true

echo "Using linuxdeploy to bundle shared libraries (including Qt6)..."
# Force linuxdeploy to include PyQt6's bundled Qt libraries, libfuse2, and their system dependencies
PYQT_LIBS=$(find "$APP_DIR/opt/photoshop-installer/venv" -name "libQt6*.so.6" -printf "--library %p ")
FUSE_LIB=$(find /lib /usr/lib -name "libfuse.so.2" | head -n 1)

EXTRA_LIBS=""
if [ -n "$FUSE_LIB" ]; then
    echo "Found libfuse2 at $FUSE_LIB, bundling it..."
    EXTRA_LIBS="--library $FUSE_LIB"
fi

./linuxdeploy --appdir "$APP_DIR" \
    --executable "$APP_DIR/opt/photoshop-installer/venv/bin/python3" \
    $PYQT_LIBS \
    $EXTRA_LIBS \
    --desktop-file "$APP_DIR/photoshop.desktop" \
    --icon-file "$APP_DIR/photoshop.png"

echo "Generating AppImage..."
export ARCH=x86_64
./appimagetool "$APP_DIR" Photoshop_Installer_x86_64.AppImage

echo "SUCCESS: Standalone AppImage created!"
