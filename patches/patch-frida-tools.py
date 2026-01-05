#!/usr/bin/env python3
"""
Patch frida-tools for Android 16 (API 36) compatibility.

This script patches the java.js bridge to fix crashes on Android 16.

Fixes applied:
1. getArtClassSpec (He) - Returns fixed offsets for API 36
2. Disable art_api C module for API 36 - Uses safer reflection path
3. Fix kt() decode function - Properly decode method/field IDs on API 36

Run this after: pip install frida-tools
"""

import sys
from pathlib import Path

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

    # Check if already fully patched
    if 'be()>=36?0:1,e.ifields' in src:
        print("[*] Already patched!")
        return 0

    # Backup
    backup = java_js.with_suffix('.js.bak')
    if not backup.exists():
        backup.write_text(src)
        print(f"[+] Backup saved to {backup}")

    changes = 0

    # Patch 1: Fix getArtClassSpec (He) to return proper offsets for API 36
    # Handle both vanilla and previously modified versions

    # Check if already patched with correct fix
    if 'He(e){if(be()>=36){return{offset:' in src:
        print("[*] He() already patched correctly")
    # Fix version that returns null for API 36
    elif 'function He(e){if(be()>=36){return null;}' in src:
        src = src.replace(
            'function He(e){if(be()>=36){return null;}',
            'function He(e){if(be()>=36){return{offset:{ifields:40,methods:48,sfields:0,copiedMethodsOffset:108}};}'
        )
        print("[+] Fixed He() - changed null return to proper offsets for API 36")
        changes += 1
    # Vanilla version - add API 36 check
    elif 'function He(e){let t=null;return e.perform' in src:
        src = src.replace(
            'function He(e){let t=null;return e.perform',
            'function He(e){if(be()>=36){return{offset:{ifields:40,methods:48,sfields:0,copiedMethodsOffset:108}};}let t=null;return e.perform'
        )
        print("[+] Fixed He() - added API 36 early return with proper offsets")
        changes += 1
    else:
        print("[!] Could not find He() pattern - unknown frida-tools version")

    # Patch 2: Disable art_api C module for API 36 (causes ToReflectedMethod crashes)
    old2 = '[1,e.ifields,e.methods,e.sfields,e.copiedMethodsOffset,n.size,n.offset.accessFlags,r.size,r.offset.accessFlags,4294967295]'
    new2 = '[be()>=36?0:1,e.ifields,e.methods,e.sfields,e.copiedMethodsOffset,n.size,n.offset.accessFlags,r.size,r.offset.accessFlags,4294967295]'
    if old2 in src:
        src = src.replace(old2, new2)
        print("[+] Disabled art_api C module for API 36")
        changes += 1
    elif 'be()>=36?0:1,e.ifields' in src:
        print("[*] art_api already disabled for API 36")
    else:
        print("[!] Could not find art_api pattern")

    # Patch 3: Fix kt() to not skip decode on API 36
    old3 = 'function kt(e,t){if(be()>=36)return e;'
    new3 = 'function kt(e,t){'
    if old3 in src:
        src = src.replace(old3, new3)
        print("[+] Fixed kt() - removed broken API 36 early return")
        changes += 1
    elif 'function kt(e,t){const' in src or 'function kt(e,t){' in src and 'if(be()>=36)return e' not in src:
        print("[*] kt() already patched or different version")
    else:
        print("[!] Could not find kt() pattern")

    if changes > 0:
        java_js.write_text(src)
        print(f"\n[+] Applied {changes} patches to {java_js}")
        print("[+] Restart frida to use the patched bridge")
    else:
        print("\n[*] No changes needed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
