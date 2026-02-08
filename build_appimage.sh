#!/bin/bash
# build_appimage.sh - Build Photoshop Installer AppImage with pre-compiled Wine 11.1
# Licensed under GNU GPL v3.0
# Copyright (C) 2026  (3ddruck12)
#
# Prerequisites:
#   - python-standalone.tar.gz  (from https://github.com/indygreg/python-build-standalone)
#   - appimagetool               (in project root or on PATH)
#   - linuxdeploy                (in project root or on PATH)
#   - Standard build tools: gcc, flex, bison, make, mingw-w64
#
# This script:
#   1. Compiles Wine 11.1 from source (once, cached)
#   2. Packages the Wine runtime + Python + PyQt6 + installer into an AppImage
#   3. The end-user does NOT need to compile anything

set -euo pipefail

APP_DIR="Photoshop.AppDir"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
WINE_SOURCE="wine-11.1"
WINE_BUILD_DIR="wine-11.1-build"
PYTHON_TAR="python-standalone.tar.gz"
APPIMAGE_NAME="Photoshop_Installer_x86_64.AppImage"

cd "$PROJECT_DIR"

# Wine's build system does not handle spaces in paths.
# We build in /tmp to avoid issues with paths like "Software Projekte".
WINE_BUILD_BASE="/tmp/wine-build-$$"

# ── Sanity checks ──────────────────────────────────────────────────────────

if [ ! -d "$WINE_SOURCE" ]; then
    echo "ERROR: Wine source directory '$WINE_SOURCE' not found."
    echo "Please place the Wine 11.1 source tree in the project root."
    exit 1
fi

if [ ! -f "$PYTHON_TAR" ]; then
    echo "ERROR: $PYTHON_TAR not found!"
    echo ""
    echo "Download a standalone Python build from:"
    echo "  https://github.com/indygreg/python-build-standalone/releases"
    echo ""
    echo "Example (Python 3.12, x86_64, Linux):"
    echo "  wget https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
    echo "  mv cpython-*.tar.gz python-standalone.tar.gz"
    exit 1
fi

for tool in gcc flex bison make; do
    if ! command -v "$tool" &>/dev/null; then
        echo "ERROR: '$tool' is required but not found. Install build dependencies first."
        exit 1
    fi
done

# MinGW cross-compilers are required for WoW64 (32-bit) support
for cross in i686-w64-mingw32-gcc x86_64-w64-mingw32-gcc; do
    if ! command -v "$cross" &>/dev/null; then
        echo "ERROR: '$cross' is required for WoW64 support."
        echo "  Debian/Ubuntu:  sudo apt install mingw-w64"
        echo "  Arch:           sudo pacman -S mingw-w64-gcc"
        echo "  Fedora:         sudo dnf install mingw64-gcc mingw32-gcc"
        exit 1
    fi
done

# ── Step 1: Compile Wine 11.1 (cached) ────────────────────────────────────

if [ -f "$WINE_BUILD_DIR/wine" ]; then
    echo "Wine 11.1 already compiled in $WINE_BUILD_DIR, skipping build."
else
    echo "=== Compiling Wine 11.1 (this takes 20-40 minutes) ==="
    echo "    Building in $WINE_BUILD_BASE to avoid spaces-in-path issues."

    rm -rf "$WINE_BUILD_DIR" "$WINE_BUILD_BASE"
    mkdir -p "$WINE_BUILD_BASE"/{src,build}

    # Copy Wine source to a space-free temp directory
    echo "Copying Wine source to temp build location..."
    cp -a "$PROJECT_DIR/$WINE_SOURCE/." "$WINE_BUILD_BASE/src/"

    # Apply Adobe Photoshop patches if they exist
    if [ -d "$PROJECT_DIR/wine-patches" ]; then
        echo "Applying Adobe Photoshop patches from wine-patches/..."
        cp -af "$PROJECT_DIR/wine-patches/." "$WINE_BUILD_BASE/src/"
    fi

    (
        cd "$WINE_BUILD_BASE/build"

        "$WINE_BUILD_BASE/src/configure" \
            --enable-archs=x86_64,i386 \
            --disable-tests \
            --prefix="$WINE_BUILD_BASE/install"

        NPROC=$(nproc 2>/dev/null || echo 4)
        # Limit parallelism to avoid OOM on low-memory systems
        NPROC=$((NPROC > 8 ? 8 : NPROC))
        echo "Building with -j${NPROC}..."
        make -j"$NPROC"
        make install
    )

    # Copy install result back to project
    mkdir -p "$WINE_BUILD_DIR"
    cp -a "$WINE_BUILD_BASE/install/." "$WINE_BUILD_DIR/install/"
    # Copy the wine binary for cache detection
    cp "$WINE_BUILD_BASE/build/wine" "$WINE_BUILD_DIR/wine" 2>/dev/null || true
    cp "$WINE_BUILD_BASE/install/bin/wine" "$WINE_BUILD_DIR/wine" 2>/dev/null || true

    # Cleanup temp build
    rm -rf "$WINE_BUILD_BASE"

    echo "=== Wine 11.1 compiled successfully ==="
fi

WINE_INSTALL="$WINE_BUILD_DIR/install"

# ── Step 2: Prepare AppDir ─────────────────────────────────────────────────

echo "=== Preparing AppDir ==="
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"/{usr/bin,usr/lib,usr/share,opt/photoshop-installer}

# Copy Wine runtime (binaries + libraries, no source/docs/headers)
echo "Copying Wine runtime..."
cp -a "$WINE_INSTALL/bin/"* "$APP_DIR/usr/bin/"
if [ -d "$WINE_INSTALL/lib64" ]; then
    cp -a "$WINE_INSTALL/lib64" "$APP_DIR/usr/"
fi
if [ -d "$WINE_INSTALL/lib" ]; then
    cp -a "$WINE_INSTALL/lib/"* "$APP_DIR/usr/lib/"
fi
if [ -d "$WINE_INSTALL/share/wine" ]; then
    cp -a "$WINE_INSTALL/share/wine" "$APP_DIR/usr/share/"
fi

# ── Step 3: Bundle Python ──────────────────────────────────────────────────

echo "Extracting standalone Python..."
tar -xf "$PYTHON_TAR" -C "$APP_DIR/usr/"
# The tarball typically extracts to 'python/' – rename if needed
if [ ! -d "$APP_DIR/usr/python" ] && [ -d "$APP_DIR/usr/install" ]; then
    mv "$APP_DIR/usr/install" "$APP_DIR/usr/python"
fi

echo "Installing PyQt6 into bundled Python..."
"$APP_DIR/usr/python/bin/python3" -m pip install --quiet PyQt6 2>/dev/null || \
"$APP_DIR/usr/python/bin/python3" -m pip install PyQt6

# ── Step 4: Copy project files ─────────────────────────────────────────────

echo "Copying installer files..."
cp "$PROJECT_DIR/PhotoshopInstaller.py" "$APP_DIR/opt/photoshop-installer/"
cp "$PROJECT_DIR/version_configs.json"  "$APP_DIR/opt/photoshop-installer/"

if [ -f "$PROJECT_DIR/pstux_icon.png" ]; then
    cp "$PROJECT_DIR/pstux_icon.png" "$APP_DIR/opt/photoshop-installer/"
    cp "$PROJECT_DIR/pstux_icon.png" "$APP_DIR/photoshop.png"
    # Resize icon (optional, requires ImageMagick)
    if command -v mogrify &>/dev/null; then
        mogrify -resize 512x512 "$APP_DIR/photoshop.png"
    else
        echo "Note: 'mogrify' not found, skipping icon resize (ImageMagick optional)."
    fi
fi

# ── Step 5: Create AppRun ──────────────────────────────────────────────────

echo "Creating AppRun..."
cat > "$APP_DIR/AppRun" << 'APPRUN_EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

# Python environment
export PYTHONHOME="$HERE/usr/python"
export PATH="$HERE/usr/python/bin:$HERE/usr/bin:$PATH"
export PYTHONPATH="$HERE/opt/photoshop-installer:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib64:$HERE/usr/python/lib:${LD_LIBRARY_PATH:-}"

# Wine environment (64-bit + 32-bit WoW64)
export WINEDLLPATH="$HERE/usr/lib64/wine/x86_64-unix:$HERE/usr/lib/wine/x86_64-unix:$HERE/usr/lib64/wine/i386-unix:$HERE/usr/lib/wine/i386-unix:${WINEDLLPATH:-}"

cd "$HERE/opt/photoshop-installer"
exec "$HERE/usr/python/bin/python3" PhotoshopInstaller.py "$@"
APPRUN_EOF
chmod +x "$APP_DIR/AppRun"

# ── Step 6: Create desktop file ───────────────────────────────────────────

echo "Creating desktop file..."
cat > "$APP_DIR/photoshop.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Type=Application
Name=Photoshop Installer for Linux
Comment=Install and manage Adobe Photoshop via Wine 11.1
Exec=AppRun
Icon=photoshop
Categories=Graphics;
DESKTOP_EOF
# Desktop files should be 644, not executable
chmod 644 "$APP_DIR/photoshop.desktop"

# ── Step 7: Bundle system libraries ───────────────────────────────────────

echo "Bundling system libraries..."
FUSE_LIB=$(find /lib /usr/lib -name "libfuse.so.2" 2>/dev/null | head -n 1)
EXTRA_LIBS=""
if [ -n "$FUSE_LIB" ]; then
    echo "Found libfuse2 at $FUSE_LIB"
    EXTRA_LIBS="--library $FUSE_LIB"
fi

if command -v ./linuxdeploy &>/dev/null || [ -f "./linuxdeploy" ]; then
    LINUXDEPLOY="./linuxdeploy"
elif command -v linuxdeploy &>/dev/null; then
    LINUXDEPLOY="linuxdeploy"
else
    echo "Warning: linuxdeploy not found. Skipping automatic library bundling."
    echo "The AppImage may be missing shared libraries on some systems."
    LINUXDEPLOY=""
fi

if [ -n "$LINUXDEPLOY" ]; then
    $LINUXDEPLOY --appdir "$APP_DIR" \
        --executable "$APP_DIR/usr/python/bin/python3" \
        $EXTRA_LIBS \
        --desktop-file "$APP_DIR/photoshop.desktop" \
        --icon-file "$APP_DIR/photoshop.png" || true
fi

# ── Step 8: Generate AppImage ─────────────────────────────────────────────

echo "=== Generating AppImage ==="
export ARCH=x86_64

if [ -f "./appimagetool" ]; then
    APPIMAGETOOL="./appimagetool"
elif command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
else
    echo "ERROR: appimagetool not found. Place it in the project root or install it."
    exit 1
fi

$APPIMAGETOOL "$APP_DIR" "$APPIMAGE_NAME"

echo ""
echo "============================================"
echo "  SUCCESS: $APPIMAGE_NAME created!"
echo "  Size: $(du -h "$APPIMAGE_NAME" | cut -f1)"
echo ""
echo "  Wine 11.1 is pre-compiled and bundled."
echo "  Users only need 'winetricks' installed."
echo "============================================"
