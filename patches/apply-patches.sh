#!/bin/bash
# Apply Android 15/16 compatibility patches for Frida
# Run this after cloning or updating submodules

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[*] Applying Android 15/16 compatibility patches..."

# Apply frida-core patch
if [ -f "$SCRIPT_DIR/001-android16-compat-spawn.patch" ]; then
    echo "[*] Applying frida-core compat spawn patch..."
    cd "$ROOT_DIR/subprojects/frida-core"
    git checkout -- src/linux/linux-host-session.vala 2>/dev/null || true
    patch -p1 < "$SCRIPT_DIR/001-android16-compat-spawn.patch"
    echo "[+] frida-core patch applied"
fi

# Apply frida-tools patch
if [ -f "$SCRIPT_DIR/002-android16-java-bridge-fix.patch" ]; then
    echo "[*] Applying frida-tools Java bridge fix patch..."
    cd "$ROOT_DIR/subprojects/frida-tools"
    git checkout -- bridges/build.py 2>/dev/null || true
    patch -p1 < "$SCRIPT_DIR/002-android16-java-bridge-fix.patch"
    echo "[+] frida-tools patch applied"
fi

echo "[+] All patches applied successfully!"
echo ""
echo "Now run: make"
