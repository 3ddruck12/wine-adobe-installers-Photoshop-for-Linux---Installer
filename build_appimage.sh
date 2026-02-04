#!/bin/bash
# build_appimage.sh - Enhanced AppImage creation with Standalone Python

set -e

APP_DIR="Photoshop.AppDir"
PROJECT_DIR=$(pwd)
WINE_SOURCE="wine-adobe-installers-fix-dropdowns"
PYTHON_TAR="python-standalone.tar.gz"

if [ ! -f "$PYTHON_TAR" ]; then
    echo "ERROR: $PYTHON_TAR not found! Download it first."
    exit 1
fi

echo "Cleanup old AppDir..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/usr"
mkdir -p "$APP_DIR/opt/photoshop-installer"

echo "Extracting Standalone Python..."
tar -xf "$PYTHON_TAR" -C "$APP_DIR/usr/"

echo "Installing PyQt6 into bundled Python..."
# Use the bundled python to install its own dependencies
"$APP_DIR/usr/python/bin/python3" -m pip install PyQt6 --quiet

echo "Copying project files..."
cp PhotoshopInstaller.py "$APP_DIR/opt/photoshop-installer/"
cp version_configs.json "$APP_DIR/opt/photoshop-installer/"
cp pstux_icon.png "$APP_DIR/opt/photoshop-installer/"
cp -r "$WINE_SOURCE" "$APP_DIR/opt/photoshop-installer/"

echo "Creating AppRun..."
cat <<EOF > "$APP_DIR/AppRun"
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PYTHONHOME="\$HERE/usr/python"
export PATH="\$HERE/usr/python/bin:\$PATH"
export PYTHONPATH="\$HERE/opt/photoshop-installer:\$PYTHONPATH"
export LD_LIBRARY_PATH="\$HERE/usr/lib:\$HERE/usr/python/lib:\$LD_LIBRARY_PATH"

# Run the installer using the bundled Python
cd "\$HERE/opt/photoshop-installer"
"\$HERE/usr/python/bin/python3" PhotoshopInstaller.py "\$@"
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

echo "Using linuxdeploy to bundle shared libraries..."
# We don't need to manually find PyQt6 libs anymore as they are in the bundled python's site-packages
# and linuxdeploy will find them via the executable.
FUSE_LIB=$(find /lib /usr/lib -name "libfuse.so.2" | head -n 1)

EXTRA_LIBS=""
if [ -n "$FUSE_LIB" ]; then
    echo "Found libfuse2 at $FUSE_LIB, bundling it..."
    EXTRA_LIBS="--library $FUSE_LIB"
fi

./linuxdeploy --appdir "$APP_DIR" \
    --executable "$APP_DIR/usr/python/bin/python3" \
    $EXTRA_LIBS \
    --desktop-file "$APP_DIR/photoshop.desktop" \
    --icon-file "$APP_DIR/photoshop.png"

echo "Generating AppImage..."
export ARCH=x86_64
./appimagetool "$APP_DIR" Photoshop_Installer_x86_64.AppImage

echo "SUCCESS: Standalone AppImage created with bundled Python!"
