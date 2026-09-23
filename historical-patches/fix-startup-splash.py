#!/usr/bin/env python3
"""Blender3GS iOS6 experimental Python IPA: skip desktop splash at startup.

This script touches only experimental source/build/binary and creates a new IPA.
It does not alter the original Touch v2 build or working IPA.
"""
from pathlib import Path
import hashlib
import os
import py_compile
import re
import shutil
import subprocess

ROOT = Path.home() / "Downloads"
SOURCE = ROOT / "blender-ios6-target/source/blender/windowmanager/intern/wm_init_exit.c"
BUILD = ROOT / "blender-ios6-build-python"
WORK = ROOT / "blender-ios6-python"
BIN = ROOT / "Blender3GS-python-armv7"
LINKER = ROOT / "blender-link-ios-python-v3.py"
PACKAGER = WORK / "Blender3GS-package-rna.py"
NEW_PACKAGER = WORK / "Blender3GS-package-nosplash.py"
OUT = ROOT / "Blender3GS-python-nosplash-test.ipa"
MARKER = "Blender3GS iOS6: skip desktop startup splash"
ANCHOR = "void WM_init_splash(bContext *C)\n{\n"
PATCH = (ANCHOR + "#ifdef WITH_IOS\n"
         "\t/* " + MARKER + "; unusable on 480x320 GLES2. */\n"
         "\t(void)C;\n"
         "\treturn;\n"
         "#endif\n")

def stop(s):
    raise SystemExit("STOP: " + s)

def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()

def run(label, args, logfile):
    print("\n=== " + label + " ===", flush=True)
    print("COMMAND:", " ".join(map(str, args)), flush=True)
    with logfile.open("w") as f:
        r = subprocess.run([str(a) for a in args], stdout=f, stderr=subprocess.STDOUT,
                           text=True)
    if r.returncode:
        print(logfile.read_text(errors="replace")[-11000:], flush=True)
        stop("exit %d; full log: %s" % (r.returncode, logfile))
    print("PASS: log:", logfile, flush=True)
    return r

print("=== 1. VERIFY EXPERIMENTAL INPUTS ===", flush=True)
for p in (SOURCE, BUILD / "build.ninja", BIN, LINKER, PACKAGER):
    if not p.is_file() or not p.stat().st_size:
        stop("missing or empty: " + str(p))
    print("PASS:", p, flush=True)
if "DEVELOPER_DIR" not in os.environ or "IOS_SDKROOT" not in os.environ:
    stop("export DEVELOPER_DIR and IOS_SDKROOT first")
WORK.mkdir(exist_ok=True, parents=True)
text = SOURCE.read_text()
if MARKER not in text:
    if text.count(ANCHOR) != 1:
        stop("unexpected WM_init_splash structure, original source NOT modified")
    backup = SOURCE.with_name("wm_init_exit.c.before-ios6-nosplash")
    if backup.exists():
        stop("backup exists but patch marker absent; check source manually: " + str(backup))
    shutil.copy2(SOURCE, backup)
    SOURCE.write_text(text.replace(ANCHOR, PATCH, 1))
    print("PATCHED:", SOURCE, flush=True)
    print("BACKUP:", backup, flush=True)
else:
    if text.count(MARKER) != 1 or PATCH not in text:
        stop("unexpected partial startup-splash patch")
    print("PASS: startup splash already patched", flush=True)

run("2. REBUILD ARMv7 WINDOW MANAGER", ["ninja", "-C", BUILD, "-j4", "bf_windowmanager"],
    WORK / "build-nosplash-windowmanager.log")

print("\n=== 3. PRESERVE OLD PYTHON EXECUTABLE ===", flush=True)
old_bin = WORK / "Blender3GS-python-before-nosplash-armv7"
if not old_bin.exists():
    shutil.copy2(BIN, old_bin)
print("BACKUP:", old_bin, flush=True)
old_sha = sha(BIN)
run("4. RELINK EXPERIMENTAL PYTHON WITH ATEXIT + RNA",
    ["python3", LINKER], WORK / "link-nosplash.log")
if not BIN.is_file() or not BIN.stat().st_size:
    stop("linker did not create executable")
if sha(BIN) == old_sha:
    stop("binary hash unchanged after relink; not packaging old executable")
print("PASS: executable SHA256 changed; new build linked", flush=True)
run("5. VERIFY ARMV7 AND ATEXIT", ["xcrun", "lipo", "-info", BIN], WORK / "nosplash-arch.log")
nm = subprocess.run(["xcrun", "nm", "-g", str(BIN)], capture_output=True, text=True)
if nm.returncode or not re.search(r"\b[Tt]\s+_PyInit_atexit\b", nm.stdout):
    stop("final executable missing defined PyInit_atexit")
print("PASS: final binary defines PyInit_atexit", flush=True)

print("\n=== 6. CREATE A SEPARATE PACKAGE SCRIPT ===", flush=True)
s = PACKAGER.read_text()
old_name = "Blender3GS-python-rna-test.ipa"
new_name = OUT.name
if s.count(old_name) != 1:
    stop("expected RNA IPA output filename not found exactly once; old binaries retained")
s = s.replace(old_name, new_name, 1)
for key, value in (("CFBundleVersion", "5"), ("CFBundleShortVersionString", "0.5.0")):
    pat = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat, s)) != 1:
        stop("unexpected package version assignment for " + key)
    s = re.sub(pat, lambda m: m.group(1) + repr(value), s, count=1)
NEW_PACKAGER.write_text(s)
py_compile.compile(str(NEW_PACKAGER), doraise=True)
print("PASS:", NEW_PACKAGER, flush=True)
run("7. PACKAGE SEPARATE IPA", ["python3", NEW_PACKAGER],
    WORK / "package-nosplash.log")
if not OUT.is_file() or not OUT.stat().st_size:
    stop("packager did not create " + str(OUT))
print("\nSUCCESS: NO-SPLASH EXPERIMENT READY", flush=True)
print("IPA:", OUT, flush=True)
print("SIZE:", round(OUT.stat().st_size / 1024 / 1024, 2), "MiB", flush=True)
print("Original Touch v2 and prior experimental IPAs were not modified.", flush=True)