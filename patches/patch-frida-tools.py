#!/usr/bin/env python3
"""
Patch frida-tools for Android 16 (API 36) compatibility.

This script patches the java.js bridge to fix crashes on Android 16.

Fixes applied:
1. getArtClassSpec (He) - Returns fixed offsets for API 36
2. Disable art_api C module for API 36 - Uses safer reflection path
   (handles both pre- and post-spread-operator minified shapes)
3. Fix kt() decode function - Properly decode method/field IDs on API 36
4. tryGetEnvJvmti (De) - Return null early on API 36
   (EnsurePluginLoaded was removed from libart.so on Android 16 — calling
    the stale .find() result crashes with "illegal instruction")
5. ensureClassInitialized - No-op on API 36
   (getClassName -> GetFieldID SIGSEGVs on API 36 for some class wrappers)

Run this after: pip install frida-tools
"""

import sys
from pathlib import Path


def patch_he(src):
    """Patch 1: getArtClassSpec (He) to return fixed offsets on API 36."""
    if 'He(e){if(be()>=36){return{offset:' in src:
        print("[*] He() already patched correctly")
        return src, 0
    # Prior-patched-to-null variant: upgrade to correct offsets.
    old = 'function He(e){if(be()>=36){return null;}'
    new = ('function He(e){if(be()>=36){return{offset:{'
           'ifields:40,methods:48,sfields:0,copiedMethodsOffset:108}};}')
    if old in src:
        print("[+] He(): replaced null-return with correct API 36 offsets")
        return src.replace(old, new, 1), 1
    # Vanilla: inject early return.
    old = 'function He(e){let t=null;return e.perform'
    new = ('function He(e){if(be()>=36){return{offset:{'
           'ifields:40,methods:48,sfields:0,copiedMethodsOffset:108}};}'
           'let t=null;return e.perform')
    if old in src:
        print("[+] He(): added API 36 early return with correct offsets")
        return src.replace(old, new, 1), 1
    print("[!] He() pattern not found - unknown frida-tools version")
    return src, 0


def patch_art_api(src):
    """Patch 2: disable art_api C module on API 36 (handles both minified shapes)."""
    if 'be()>=36?0:1,e.ifields' in src or 'be()>=36?0:1,...e,o.size' in src:
        print("[*] art_api already disabled for API 36")
        return src, 0
    # Old shape (pre-spread operator): individual property access.
    old = ('[1,e.ifields,e.methods,e.sfields,e.copiedMethodsOffset,'
           'n.size,n.offset.accessFlags,r.size,r.offset.accessFlags,4294967295]')
    new = ('[be()>=36?0:1,e.ifields,e.methods,e.sfields,e.copiedMethodsOffset,'
           'n.size,n.offset.accessFlags,r.size,r.offset.accessFlags,4294967295]')
    if old in src:
        print("[+] art_api C module disabled on API 36 (legacy shape)")
        return src.replace(old, new, 1), 1
    # New shape (frida-tools ~14.5+): spread operator + differently-named locals.
    old = ('[1,...e,o.size,o.offset.accessFlags,'
           'i.size,i.offset.accessFlags,4294967295]')
    new = ('[be()>=36?0:1,...e,o.size,o.offset.accessFlags,'
           'i.size,i.offset.accessFlags,4294967295]')
    if old in src:
        print("[+] art_api C module disabled on API 36 (spread shape)")
        return src.replace(old, new, 1), 1
    print("[!] art_api pattern not found - likely a new minified shape")
    return src, 0


def patch_kt(src):
    """Patch 3: remove broken API 36 early-return in kt()."""
    old = 'function kt(e,t){if(be()>=36)return e;'
    if old in src:
        print("[+] kt(): removed broken API 36 early return")
        return src.replace(old, 'function kt(e,t){', 1), 1
    if 'function kt(e,t){const' in src:
        print("[*] kt() already correct or different version")
        return src, 0
    print("[!] kt() pattern not found")
    return src, 0


def patch_jvmti(src):
    """Patch 4: tryGetEnvJvmti (De) returns null early.

    EnsurePluginLoaded symbol was removed from libart.so on Android 16;
    Module.find() returns a stale address and NativeFunction call crashes.
    """
    if 'function De(e,t){return null;' in src:
        print("[*] De (tryGetEnvJvmti) already patched")
        return src, 0
    old = 'function De(e,t){let n=null;return e.perform'
    new = 'function De(e,t){return null;e.perform'
    if old in src:
        print("[+] De (tryGetEnvJvmti) returns null early — skips dead JVMTI path")
        return src.replace(old, new, 1), 1
    print("[!] De() pattern not found")
    return src, 0


def patch_ensure_class_initialized(src):
    """Patch 5: ensureClassInitialized no-op on API 36.

    getClassName internally calls GetFieldID which SIGSEGVs on API 36
    for some class wrappers. Per the bridge, ensureClassInitialized is
    only an optimization; skipping is safe.
    """
    if 'zed:function(e,t){if(be()>=36)return;' in src:
        print("[*] ensureClassInitialized (zed) already patched")
        return src, 0
    old = 'zed:function(e,t){"art"===Fe().flavor&&e.getClassName(t)}'
    new = 'zed:function(e,t){if(be()>=36)return;"art"===Fe().flavor&&e.getClassName(t)}'
    if old in src:
        print("[+] ensureClassInitialized (zed) no-op on API 36")
        return src.replace(old, new, 1), 1
    print("[!] ensureClassInitialized pattern not found")
    return src, 0


def main():
    try:
        import frida_tools
    except ImportError:
        print("ERROR: frida-tools not installed. Run: pip install frida-tools")
        return 1

    java_js = Path(frida_tools.__file__).parent / "bridges" / "java.js"
    if not java_js.exists():
        print(f"ERROR: java.js not found at {java_js}")
        return 1

    src = java_js.read_text()
    backup = java_js.with_suffix('.js.bak')
    if not backup.exists():
        backup.write_text(src)
        print(f"[+] Backup saved to {backup}")

    changes = 0
    for patcher in (patch_he, patch_art_api, patch_kt,
                    patch_jvmti, patch_ensure_class_initialized):
        src, n = patcher(src)
        changes += n

    if changes > 0:
        java_js.write_text(src)
        print(f"\n[+] Applied {changes} patches to {java_js}")
        print("[+] Restart frida-server on the device to pick up the patched bridge")
    else:
        print("\n[*] No changes needed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
