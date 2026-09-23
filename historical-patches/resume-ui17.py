#!/usr/bin/env python3
"""Resume an ALREADY APPLIED Blender3GS UI17 experiment safely.

Does not reapply source edits or overwrite an existing IPA. It only rebuilds,
relinks, and packages when source markers prove UI17 was applied to BOTH files.
This file is meant to run on the user's Mac, not in the sandbox.
"""
from pathlib import Path
import hashlib
import os
import plistlib
import py_compile
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home() / 'Downloads')))
SRC = ROOT / 'blender-ios6-target'
WORK = ROOT / 'blender-ios6-python'
BUILD = ROOT / 'blender-ios6-build-python'
STYLE = SRC / 'source/blender/editors/interface/interface_style.c'
BUTTONS = SRC / 'source/blender/editors/space_buttons/space_buttons.c'
HEADER = SRC / 'source/blender/editors/space_buttons/buttons_header.c'
WM = SRC / 'source/blender/windowmanager/intern/wm_files.c'
EXE = ROOT / 'Blender3GS-python-armv7'
LINK = ROOT / 'blender-link-ios-python-v3.py'
PACK16 = WORK / 'Blender3GS-package-ui-v16.py'
PACK17 = WORK / 'Blender3GS-package-ui-v17.py'
IPA = ROOT / 'Blender3GS-python-ui-v17-properties-text.ipa'
PREV = WORK / 'Blender3GS-python-before-ui-v17-armv7'
TAG = 'BLENDER3GS_UI17_PROPERTIES_TEXT_20260923'


def fail(message):
    raise SystemExit('STOP: ' + message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label, cmd, filename):
    print('\n=== ' + label + ' ===\nCOMMAND:', ' '.join(map(str, cmd)), flush=True)
    with filename.open('w') as out:
        result = subprocess.run(list(map(str, cmd)), stdout=out, stderr=subprocess.STDOUT)
    if result.returncode:
        print(filename.read_text(errors='replace')[-18000:])
        fail('%s failed (%d); see %s' % (label, result.returncode, filename))
    print('PASS:', filename, flush=True)


def verify_ipa(path):
    if not path.is_file() or path.stat().st_size < 1000000:
        fail('IPA missing or unexpectedly small: ' + str(path))
    with zipfile.ZipFile(path) as z:
        broken = z.testzip()
        if broken:
            fail('ZIP CRC failed for ' + broken)
        if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():
            fail('IPA lacks the app executable')
        plistname = 'Payload/Blender3GS.app/Info.plist'
        if plistname not in z.namelist():
            fail('IPA lacks Info.plist')
        info = plistlib.loads(z.read(plistname))
        if info.get('CFBundleIdentifier') != 'io.arutiunio.blender3gs.python' or str(info.get('CFBundleVersion')) != '17':
            fail('IPA bundle ID/version is not the expected Blender Py UI17')
    print('PASS: valid UI17 IPA:', path, 'size:', path.stat().st_size, 'bytes', flush=True)


print('=== 1. VERIFY APPLIED UI17 SOURCE ===', flush=True)
for p in (STYLE, BUTTONS, HEADER, WM, BUILD / 'build.ninja', EXE, LINK, PACK16):
    if not p.is_file() or not p.stat().st_size:
        fail('missing/empty file: ' + str(p))
    print('PASS:', p, flush=True)
style = STYLE.read_text()
buttons = BUTTONS.read_text()
if TAG not in style or TAG not in buttons:
    fail('UI17 marker must be present in BOTH interface_style.c and space_buttons.c; do not mix versions')
if 'BLI_str_utf8_size(cursor)' not in style or 'Blender3GS UI17 PROPERTIES:' not in buttons:
    fail('UI17 source content is not the expected font+Properties diagnostic patch')
if 'BLENDER3GS_UI16_REAL_PROPERTIES_20260923' not in HEADER.read_text() or 'BLENDER3GS_UI16_REAL_PROPERTIES_20260923' not in WM.read_text():
    fail('UI16 layout source not found')
if IPA.exists():
    verify_ipa(IPA)
    print('\nALREADY PACKAGED: no source, executable, or IPA overwritten.', flush=True)
    raise SystemExit(0)
if not (os.environ.get('DEVELOPER_DIR') and os.environ.get('IOS_SDKROOT')):
    fail('export DEVELOPER_DIR and IOS_SDKROOT')
WORK.mkdir(parents=True, exist_ok=True)

print('\n=== 2. BUILD EXISTING UI17 PATCH ===', flush=True)
old_hash = sha(EXE)
if not PREV.exists():
    shutil.copy2(EXE, PREV)
    print('BACKUP:', PREV, flush=True)
run('BUILD FONT + PROPERTIES', ['ninja', '-C', BUILD, '-j4', 'bf_editor_interface', 'bf_editor_space_buttons'], WORK / 'ui-v17-build.log')
run('RELINK UI17', ['python3', LINK], WORK / 'ui-v17-link.log')
new_hash = sha(EXE)
if PREV.exists() and sha(PREV) == new_hash:
    fail('new binary matches pre-UI17 backup; refuse to package a stale build')
if old_hash == new_hash:
    print('NOTICE: relinked executable hash unchanged; checking against pre-UI17 backup.', flush=True)
run('VERIFY ARMv7', ['xcrun', 'lipo', '-info', EXE], WORK / 'ui-v17-arch.log')
if 'armv7' not in (WORK / 'ui-v17-arch.log').read_text():
    fail('not an ARMv7 executable')

print('\n=== 3. PREPARE UI17 PACKAGER ===', flush=True)
if PACK17.exists():
    code = PACK17.read_text()
    if IPA.name not in code or "info['CFBundleVersion'] = '17'" not in code:
        fail('existing UI17 packager differs; refusing to overwrite it')
    print('REUSE:', PACK17, flush=True)
else:
    code = PACK16.read_text()
    source_name = 'Blender3GS-python-ui-v16-properties.ipa'
    if code.count(source_name) != 1:
        fail('UI16 package output filename expected once, found %d' % code.count(source_name))
    code = code.replace(source_name, IPA.name, 1)
    for key, value in [('CFBundleVersion', '17'), ('CFBundleShortVersionString', '0.17.0')]:
        pattern = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
        if len(re.findall(pattern, code)) != 1:
            fail('unknown package version field: ' + key)
        code = re.sub(pattern, lambda m: m.group(1) + repr(value), code, count=1)
    PACK17.write_text(code)
    py_compile.compile(str(PACK17), doraise=True)
    print('CREATED:', PACK17, flush=True)

print('\n=== 4. PACKAGE UI17 ===', flush=True)
run('PACKAGE', ['python3', PACK17], WORK / 'ui-v17-package.log')
verify_ipa(IPA)
print('\nSUCCESS: UI17 DEVICE TEST CANDIDATE:', IPA, flush=True)
print('Expected syslog marker: Blender3GS UI17 PROPERTIES', flush=True)
print('Touch v2, UI16 IPA, and existing source changes preserved.', flush=True)