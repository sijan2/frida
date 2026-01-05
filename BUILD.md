# Building Frida with Android 15/16 Patches

## Prerequisites

- macOS, Linux, or Windows with WSL
- Python 3.8+
- Node.js 18+
- Git

### macOS

```bash
brew install python node meson ninja
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install python3 python3-pip nodejs npm meson ninja-build
```

## Building frida-server (Android arm64)

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/sijan2/frida.git
cd frida
git checkout android16-compat-spawn

# Apply patches
./patches/apply-patches.sh

# Build for Android arm64
make FRIDA_HOST=android-arm64

# Output: build/subprojects/frida-core/server/frida-server
```

## Building frida-tools (Python wheel)

The Python frida-tools package needs a runtime patch for the Java bridge.

### Option 1: Patch installed frida-tools

```bash
# Install frida-tools normally
pip install frida-tools

# Find and patch java.js
JAVA_JS=$(python -c "import frida_tools; import os; print(os.path.join(os.path.dirname(frida_tools.__file__), 'bridges', 'java.js'))")

# Apply the Android 16 fix (run this Python script)
python3 << 'EOF'
import re
import sys
from pathlib import Path

try:
    import frida_tools
except ImportError:
    print("frida-tools not installed")
    sys.exit(1)

java_js = Path(frida_tools.__file__).parent / "bridges" / "java.js"
if not java_js.exists():
    print(f"java.js not found at {java_js}")
    sys.exit(1)

src = java_js.read_text()

# Find getArtClassSpec function and add API 36 override
pattern = r'(function\s+\w+\s*\([^)]*vm[^)]*\)\s*\{[^}]*MAX_OFFSET\s*=\s*0x100)'
if not re.search(pattern, src):
    print("Could not find getArtClassSpec pattern - may already be patched or different version")
    sys.exit(0)

# Add early return for API 36
patch = '''function he(e){if(getAndroidApiLevel()>=36)return{offset:{ifields:40,methods:48,sfields:0,copiedMethodsOffset:108}};const t=256'''

# Try to find the minified version
if 'function he(e){const t=256' in src:
    src = src.replace('function he(e){const t=256', patch)
    java_js.write_text(src)
    print(f"[+] Patched {java_js}")
else:
    print("Pattern not found - check frida-tools version")
EOF
```

### Option 2: Build frida-tools from source

```bash
cd frida/subprojects/frida-tools

# Apply the build patch
patch -p1 < ../../patches/002-android16-java-bridge-fix.patch

# Install in development mode
pip install -e .

# Or build wheel
pip install build
python -m build --wheel
# Output: dist/frida_tools-*.whl
```

### Option 3: Use the patched venv

If you already have a working patched installation:

```bash
# Copy the patched java.js
cp /path/to/patched/.venv/lib/python3.x/site-packages/frida_tools/bridges/java.js \
   ~/.local/lib/python3.x/site-packages/frida_tools/bridges/java.js
```

## Verifying the Fix

```bash
# Start frida-server on device
adb push build/subprojects/frida-core/server/frida-server /data/local/tmp/
adb shell "su -c 'chmod +x /data/local/tmp/frida-server'"
adb shell "su -c '/data/local/tmp/frida-server -D &'"

# Test Java.perform
frida -U -n com.android.settings -e 'Java.perform(function(){console.log("OK:", Java.use("java.lang.Thread").class)})'

# Test spawn
frida -U -f com.android.settings -e 'Java.perform(function(){console.log("Spawned OK")})'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FRIDA_ANDROID_ZYGOTE_INJECTION` | `0` on API 35+ | Set to `1` to force zygote injection |
| `FRIDA_ANDROID_SYSTEM_SERVER_AGENT` | `0` on API 35+ | Set to `1` to force system_server agent |

## Troubleshooting

### "connection is closed" after hooking

The Java bridge may still crash on some methods. Check `adb logcat` for SIGSEGV in `libart.so`.
If this happens, the `ensureClassInitialized` call may need to be disabled - update the java.js patch.

### Device UI freezes

You enabled zygote injection on API 35+. Reboot and don't set `FRIDA_ANDROID_ZYGOTE_INJECTION=1`.

### Spawn times out

The app may be slow to start. Increase the timeout in `spawn_android_compat` (default: 20s).
