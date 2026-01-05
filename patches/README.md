# Frida Android 15/16 Compatibility Patches

These patches fix Frida for Android 15 (API 35) and Android 16 (API 36) devices.

## Quick Start (Easiest Method)

If you already have frida-tools installed via pip:

```bash
# Download and run the patch script
curl -O https://raw.githubusercontent.com/sijan2/frida/android16-compat-spawn/patches/patch-frida-tools.py
python3 patch-frida-tools.py

# Download pre-built server from releases
# https://github.com/sijan2/frida/releases/tag/v17.5.2-android16
```

## Problems Fixed

### 1. Server Crash / Device Brick (frida-core)

On Android 15/16, Frida's default spawn mechanism injects into `zygote` and `system_server`. This causes:
- "Failed to reach single-threaded state in zygote" errors
- ActivityManager / system_server hangs
- Device UI becomes unresponsive

**Fix:** Added a "compat spawn" path that:
- Detects API level and disables zygote/system_server injection on API 35+
- Launches apps via `am`/`monkey` commands instead
- Polls for PID and returns it to Frida
- Environment variables `FRIDA_ANDROID_ZYGOTE_INJECTION=1` and `FRIDA_ANDROID_SYSTEM_SERVER_AGENT=1` can override this

### 2. Java.perform() Crash (frida-java-bridge)

On Android 16, the ART runtime changed significantly:
- Method array headers are 8 bytes (pointer-aligned)
- Class offsets changed (ifields=0x28, methods=0x30)
- The art_api C module causes ToReflectedMethod crashes

**Fix:** Three patches to java.js:
1. `getArtClassSpec` - Returns fixed offsets for API 36
2. `art_api` - Disabled for API 36 (uses safer reflection path)
3. `kt()` - Properly decodes method/field IDs on API 36

## How to Apply

### Option 1: Patch existing frida-tools installation

```bash
python3 patches/patch-frida-tools.py
```

### Option 2: Build from source

```bash
# After cloning this fork:
./patches/apply-patches.sh

# Then build normally:
make
```

## Building from Source

```bash
# Clone this fork
git clone --recurse-submodules https://github.com/sijan2/frida.git
cd frida
git checkout android16-compat-spawn

# Apply patches
./patches/apply-patches.sh

# Build for Android arm64
make FRIDA_HOST=android-arm64

# The server binary will be at:
# build/subprojects/frida-core/server/frida-server
```

## Deploying to Device

```bash
adb push build/subprojects/frida-core/server/frida-server /data/local/tmp/
adb shell "su -c 'chmod +x /data/local/tmp/frida-server'"
adb shell "su -c '/data/local/tmp/frida-server -D &'"
```

## Usage

```bash
# Attach to running app
frida -U -n com.example.app -l script.js

# Spawn app (uses compat spawn on Android 15/16)
frida -U -f com.example.app -l script.js
```

## Limitations of Compat Spawn

- Early startup hooks may miss some initialization code (app is already running when attached)
- No spawn gating support
- To force the old behavior (at your own risk): `export FRIDA_ANDROID_ZYGOTE_INJECTION=1`

## Files Changed

- `subprojects/frida-core/src/linux/linux-host-session.vala` - Compat spawn implementation
- `subprojects/frida-tools/bridges/build.py` - Build-time Java bridge patch
- `patches/patch-frida-tools.py` - Runtime patch for installed frida-tools
