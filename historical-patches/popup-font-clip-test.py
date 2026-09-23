#!/usr/bin/env python3
"""Reversible A/B diagnostic for missing popup text on Blender 3GS iOS6.

Temporarily disables BLF's CPU glyph clipping inside uiStyleFontDrawExt on iOS only.
Does NOT claim this is the actual fix. Does not touch working Touch-v2 IPA/build.
"""
from pathlib import Path
import hashlib
import os
import py_compile
import re
import shutil
import subprocess
import zipfile

R = Path.home() / 'Downloads'
S = R / 'blender-ios6-target/source/blender/editors/interface/interface_style.c'
B = R / 'blender-ios6-build-python'
W = R / 'blender-ios6-python'
BIN = R / 'Blender3GS-python-armv7'
LINKER = R / 'blender-link-ios-python-v3.py'
PKG = W / 'Blender3GS-package-cleanui.py'
NEWPKG = W / 'Blender3GS-package-popupclip.py'
OUT = R / 'Blender3GS-python-popupclip-test.ipa'
BAK = S.with_name('interface_style.c.before-ios6-popupclip-test')
MARK = 'Blender3GS iOS6 POPUP FONT CLIPPING A/B TEST'
OLD_A = '\tBLF_clipping(fs->uifont_id, rect->xmin - 1, rect->ymin - 4, rect->xmax + 1, rect->ymax + 4);\n\tBLF_enable(fs->uifont_id, BLF_CLIPPING);'
OLD_B = '\tBLF_draw(fs->uifont_id, str, BLF_DRAW_STR_DUMMY_MAX);\n\tBLF_disable(fs->uifont_id, BLF_CLIPPING);'


def die(reason):
    raise SystemExit('STOP: ' + reason)


def run(title, cmd, logfile):
    print('\n=== ' + title + ' ===', flush=True)
    print('COMMAND:', ' '.join(str(c) for c in cmd), flush=True)
    with logfile.open('w') as f:
        p = subprocess.run([str(c) for c in cmd], stdout=f, stderr=subprocess.STDOUT)
    if p.returncode:
        print(logfile.read_text(errors='replace')[-11000:], flush=True)
        die('%s failed; full log: %s' % (title, logfile))
    print('PASS:', logfile, flush=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


print('=== 1. INPUTS ===', flush=True)
for p in (S, B / 'build.ninja', BIN, LINKER, PKG):
    if not p.is_file() or not p.stat().st_size:
        die('missing/empty: ' + str(p))
    print('PASS:', p, flush=True)
if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):
    die('export DEVELOPER_DIR and IOS_SDKROOT first')
W.mkdir(parents=True, exist_ok=True)

print('\n=== 2. PATCH ONLY STANDARD FONT DRAW (iOS A/B TEST) ===', flush=True)
s = S.read_text()
start = s.find('void uiStyleFontDrawExt(')
end = s.find('\nvoid uiStyleFontDraw(', start)
if start < 0 or end < 0:
    die('unexpected interface_style.c function boundaries; nothing changed')
part = s[start:end]
if MARK not in s:
    if BAK.exists():
        die('backup already exists but patch marker missing; inspect before proceeding: ' + str(BAK))
    if part.count(OLD_A) != 1 or part.count(OLD_B) != 1:
        die('expected BLF clipping/draw code not found once; nothing changed')
    part = part.replace(OLD_A, '#ifndef WITH_IOS\n\t/* Normal behavior on non-iOS targets. */\n' + OLD_A + '\n#else\n\t/* ' + MARK + ': suppress clipping to test popup geometry. */\n#endif', 1)
    part = part.replace(OLD_B, '\tBLF_draw(fs->uifont_id, str, BLF_DRAW_STR_DUMMY_MAX);\n#ifndef WITH_IOS\n\tBLF_disable(fs->uifont_id, BLF_CLIPPING);\n#endif', 1)
    shutil.copy2(S, BAK)
    S.write_text(s[:start] + part + s[end:])
    print('PATCHED:', S, flush=True)
    print('BACKUP:', BAK, flush=True)
else:
    if s.count(MARK) != 1:
        die('partial patch detected')
    print('PASS: A/B patch already present', flush=True)

previous = W / 'Blender3GS-python-before-popupclip-armv7'
if not previous.exists():
    shutil.copy2(BIN, previous)
print('Previous experimental executable:', previous, flush=True)
old_hash = digest(BIN)

run('3. BUILD INTERFACE', ['ninja', '-C', B, '-j4', 'bf_editor_interface'], W / 'popupclip-interface.log')
run('4. RELINK PYTHON+RNA+ATEXIT', ['python3', LINKER], W / 'popupclip-link.log')
if not BIN.is_file() or digest(BIN) == old_hash:
    die('experimental binary unchanged; no IPA will be made')
nm = subprocess.run(['xcrun', 'nm', '-g', str(BIN)], capture_output=True, text=True)
if nm.returncode or not re.search(r'\b[Tt]\s+_PyInit_atexit\b', nm.stdout):
    die('new binary missing defined PyInit_atexit')
run('5. VERIFY ARMV7', ['xcrun', 'lipo', '-info', BIN], W / 'popupclip-arch.log')

print('\n=== 6. MAKE SEPARATE IPA PACKAGER ===', flush=True)
pkg = PKG.read_text()
old_name = 'Blender3GS-python-cleanui-test.ipa'
if pkg.count(old_name) != 1:
    die('unexpected clean-UI packager output path; nothing packaged')
pkg = pkg.replace(old_name, OUT.name, 1)
for key, version in (('CFBundleVersion', '7'), ('CFBundleShortVersionString', '0.7.0')):
    regex = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(regex, pkg)) != 1:
        die('unrecognized version field ' + key + '; nothing packaged')
    pkg = re.sub(regex, lambda m: m.group(1) + repr(version), pkg, count=1)
NEWPKG.write_text(pkg)
py_compile.compile(str(NEWPKG), doraise=True)
run('7. PACKAGE POPUP CLIPPING A/B TEST', ['python3', NEWPKG], W / 'popupclip-package.log')
if not OUT.is_file():
    die('missing expected IPA: ' + str(OUT))
with zipfile.ZipFile(OUT) as z:
    bad = z.testzip()
    if bad:
        die('corrupt IPA member: ' + bad)
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():
        die('missing executable in IPA')
print('\nSUCCESS: diagnostic IPA:', OUT, flush=True)
print('IMPORTANT: This is an A/B test, NOT a confirmed popup-text fix.', flush=True)
print('Working Touch-v2 IPA/build were not modified.', flush=True)