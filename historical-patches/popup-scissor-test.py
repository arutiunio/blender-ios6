#!/usr/bin/env python3
"""Blender 3GS iOS6: restore negative BLF clip A/B, test GL scissor on popup regions.

Only alters the Python experiment sources/build. Keeps original Touch-v2 IPA unchanged.
A diagnostic test, not a claim of a popup rendering fix.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import hashlib
import py_compile
import zipfile

R = Path.home() / 'Downloads'
S = R / 'blender-ios6-target'
B = R / 'blender-ios6-build-python'
W = R / 'blender-ios6-python'
FONT = S / 'source/blender/editors/interface/interface_style.c'
REGION = S / 'source/blender/editors/interface/interface_regions.c'
FONT_BAK = FONT.with_name('interface_style.c.before-ios6-popupclip-test')
REGION_BAK = REGION.with_name('interface_regions.c.before-ios6-popup-scissor-test')
BIN = R / 'Blender3GS-python-armv7'
LINKER = R / 'blender-link-ios-python-v3.py'
PKG = W / 'Blender3GS-package-cleanui.py'
NEWPKG = W / 'Blender3GS-package-popup-scissor.py'
IPA = R / 'Blender3GS-python-popup-scissor-test.ipa'
FONT_MARK = 'Blender3GS iOS6 POPUP FONT CLIPPING A/B TEST'
REGION_MARK = 'Blender3GS iOS6 POPUP GL SCISSOR A/B TEST'


def stop(message):
    raise SystemExit('STOP: ' + message)


def run(title, args, log):
    print('\n=== ' + title + ' ===', flush=True)
    print('COMMAND:', ' '.join(map(str, args)), flush=True)
    with log.open('w') as f:
        p = subprocess.run(list(map(str, args)), stdout=f, stderr=subprocess.STDOUT)
    if p.returncode:
        print(log.read_text(errors='replace')[-13000:], flush=True)
        stop('exit %s. Full log: %s' % (p.returncode, log))
    print('PASS:', log, flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


print('=== 1. VERIFY FILES (PYTHON EXPERIMENT ONLY) ===', flush=True)
for p in (FONT, REGION, B / 'build.ninja', BIN, LINKER, PKG):
    if not p.is_file() or not p.stat().st_size:
        stop('missing/empty: ' + str(p))
    print('PASS:', p, flush=True)
if not os.getenv('DEVELOPER_DIR') or not os.getenv('IOS_SDKROOT'):
    stop('set DEVELOPER_DIR and IOS_SDKROOT')
W.mkdir(parents=True, exist_ok=True)

print('\n=== 2. UNDO FAILED FONT-CLIPPING HYPOTHESIS ===', flush=True)
font_text = FONT.read_text()
if FONT_MARK in font_text:
    if font_text.count(FONT_MARK) != 1 or not FONT_BAK.is_file():
        stop('missing/ambiguous original font backup; no files modified')
    original = FONT_BAK.read_text()
    if FONT_MARK in original or original.count('BLF_enable(fs->uifont_id, BLF_CLIPPING);') < 1:
        stop('original font backup is not valid; no files modified')
    # Confirm that the only change within the function matches our previous test.
    start = font_text.find('void uiStyleFontDrawExt(')
    end = font_text.find('\nvoid uiStyleFontDraw(', start)
    ostart = original.find('void uiStyleFontDrawExt(')
    oend = original.find('\nvoid uiStyleFontDraw(', ostart)
    if min(start, end, ostart, oend) < 0:
        stop('unexpected font function bounds; no files modified')
    candidate = font_text[:start] + original[ostart:oend] + font_text[end:]
    if candidate != original:
        stop('other interface_style.c edits since font experiment; refusing wholesale restore')
    FONT.write_text(original)
    print('RESTORED:', FONT, '(from verified backup)', flush=True)
else:
    print('PASS: font clipping experiment already absent', flush=True)

print('\n=== 3. ISOLATED POPUP GL SCISSOR TEST ===', flush=True)
text = REGION.read_text()
old = '''static void ui_block_region_draw(const bContext *C, ARegion *ar)
{
\tuiBlock *block;

\tfor (block = ar->uiblocks.first; block; block = block->next)
\t\tuiDrawBlock(C, block);
}'''
new = '''static void ui_block_region_draw(const bContext *C, ARegion *ar)
{
\tuiBlock *block;
#ifdef WITH_IOS
\t/* Blender3GS iOS6 POPUP GL SCISSOR A/B TEST.
\t * Only disable GPU scissor during a temporary popup region's draw.
\t * Keep CPU-side BLF clipping restored to its original behavior. */
\tconst GLboolean old_scissor = glIsEnabled(GL_SCISSOR_TEST);
\tstatic int log_count = 0;
\tif (log_count < 6) {
\t\tGLint viewport[4] = {0, 0, 0, 0};
\t\tGLint scissor[4] = {0, 0, 0, 0};
\t\tglGetIntegerv(GL_VIEWPORT, viewport);
\t\tglGetIntegerv(GL_SCISSOR_BOX, scissor);
\t\tsyslog(LOG_WARNING,
\t\t       "Blender3GS POPUP TEST: region=(%d,%d)-(%d,%d) "
\t\t       "viewport=(%d,%d,%d,%d) scissor_enabled=%d "
\t\t       "scissor=(%d,%d,%d,%d)",
\t\t       ar->winrct.xmin, ar->winrct.ymin,
\t\t       ar->winrct.xmax, ar->winrct.ymax,
\t\t       viewport[0], viewport[1], viewport[2], viewport[3],
\t\t       (int)old_scissor,
\t\t       scissor[0], scissor[1], scissor[2], scissor[3]);
\t\tlog_count++;
\t}
\tglDisable(GL_SCISSOR_TEST);
#endif
\tfor (block = ar->uiblocks.first; block; block = block->next)
\t\tuiDrawBlock(C, block);
#ifdef WITH_IOS
\tif (old_scissor) glEnable(GL_SCISSOR_TEST);
#endif
}'''
if REGION_MARK not in text:
    if text.count(old) != 1 or REGION_BAK.exists():
        stop('unexpected popup draw function/backup; no region source modified')
    # Header is only needed for targeted diagnostic syslog messages.
    insert = '#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n'
    anchor = '#include <assert.h>\n'
    if text.count(anchor) != 1:
        stop('unexpected interface_regions.c includes; no region source modified')
    changed = text.replace(anchor, anchor + insert, 1).replace(old, new, 1)
    shutil.copy2(REGION, REGION_BAK)
    REGION.write_text(changed)
    print('PATCHED:', REGION, flush=True)
    print('BACKUP:', REGION_BAK, flush=True)
else:
    if text.count(REGION_MARK) != 1:
        stop('ambiguous existing popup diagnostic patch')
    print('PASS: popup scissor A/B already applied', flush=True)

old_hash = digest(BIN)
backup_bin = W / 'Blender3GS-python-before-popup-scissor-armv7'
if not backup_bin.exists():
    shutil.copy2(BIN, backup_bin)
print('Saved prior experimental binary:', backup_bin, flush=True)

run('4. REBUILD INTERFACE (RESTORED BLF + POPUP TEST)',
    ['ninja', '-C', B, '-j4', 'bf_editor_interface'],
    W / 'popup-scissor-build.log')
run('5. RELINK PYTHON + RNA + ATEXIT', ['python3', LINKER], W / 'popup-scissor-link.log')
if digest(BIN) == old_hash:
    stop('binary unchanged; do not package a stale binary')
run('6. VERIFY ARMV7', ['xcrun', 'lipo', '-info', BIN], W / 'popup-scissor-arch.log')
nm = subprocess.run(['xcrun', 'nm', '-g', str(BIN)], capture_output=True, text=True)
if nm.returncode or not re.search(r'\b[Tt]\s+_PyInit_atexit\b', nm.stdout):
    stop('new binary lacks PyInit_atexit')

print('\n=== 7. PACKAGE AS SEPARATE IPA ===', flush=True)
pkg_text = PKG.read_text()
old_name = 'Blender3GS-python-cleanui-test.ipa'
if pkg_text.count(old_name) != 1:
    stop('unknown clean-UI packager output path')
pkg_text = pkg_text.replace(old_name, IPA.name, 1)
for key, val in (('CFBundleVersion', '8'), ('CFBundleShortVersionString', '0.8.0')):
    pat = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat, pkg_text)) != 1:
        stop('unknown packager version field: ' + key)
    pkg_text = re.sub(pat, lambda m: m.group(1) + repr(val), pkg_text, count=1)
NEWPKG.write_text(pkg_text)
py_compile.compile(str(NEWPKG), doraise=True)
run('8. BUILD IPA', ['python3', NEWPKG], W / 'popup-scissor-package.log')
if not IPA.is_file():
    stop('IPA missing: ' + str(IPA))
with zipfile.ZipFile(IPA) as z:
    bad = z.testzip()
    if bad:
        stop('corrupted IPA member: ' + bad)
print('\nSUCCESS: DIAGNOSTIC IPA:', IPA, flush=True)
print('Open one popup and capture syslog lines with: Blender3GS POPUP TEST', flush=True)
print('No Touch-v2 build or IPA was changed.', flush=True)