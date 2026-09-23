#!/usr/bin/env python3
"""Blender3GS / iOS 6: reversible popup button-width A/B diagnostic.

Restores the previous popup GL scissor experiment after verifying its exact
source diff; logs original menu item width, actual button rectangle, clipping
result; only for iOS popup BUTTON items, temporarily draws the unshortened text.
Never edits the working Touch-v2 source, binary, or IPA.
"""
from pathlib import Path
import ast
import hashlib
import os
import py_compile
import re
import shutil
import subprocess
import sys
import zipfile

R = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home() / 'Downloads')))
S = R / 'blender-ios6-target/source/blender/editors/interface'
W = R / 'blender-ios6-python'
B = R / 'blender-ios6-build-python'
WIDGETS = S / 'interface_widgets.c'
REGION = S / 'interface_regions.c'
REGION_BAK = S / 'interface_regions.c.before-ios6-popup-scissor-test'
WIDGETS_BAK = S / 'interface_widgets.c.before-ios6-popup-width-test'
SCISSOR_SCRIPT = R / 'Blender3GS-popup-scissor-test.py'
EXE = R / 'Blender3GS-python-armv7'
LINKER = R / 'blender-link-ios-python-v3.py'
PACKAGER = W / 'Blender3GS-package-cleanui.py'
NEW_PACKAGER = W / 'Blender3GS-package-popup-width.py'
IPA = R / 'Blender3GS-python-popup-width-test.ipa'
MARK = 'Blender3GS iOS6 POPUP TEXT WIDTH A/B TEST'
SCISSOR_MARK = 'Blender3GS iOS6 POPUP GL SCISSOR A/B TEST'
PREPARE_ONLY = '--prepare-only' in sys.argv


def stop(reason):
    raise SystemExit('STOP: ' + reason)


def run(name, args, logfile):
    print('\n=== ' + name + ' ===', flush=True)
    print('COMMAND:', ' '.join(map(str, args)), flush=True)
    with logfile.open('w') as stream:
        p = subprocess.run(list(map(str, args)), stdout=stream, stderr=subprocess.STDOUT)
    if p.returncode:
        print(logfile.read_text(errors='replace')[-14000:], flush=True)
        stop('exit %d; full log: %s' % (p.returncode, logfile))
    print('PASS:', logfile, flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


print('=== 1. CHECK ONLY EXPERIMENTAL SOURCES ===', flush=True)
for path in (WIDGETS, REGION, REGION_BAK, SCISSOR_SCRIPT,
             B / 'build.ninja', EXE, LINKER, PACKAGER):
    if not path.is_file() or not path.stat().st_size:
        stop('missing/empty: ' + str(path))
    print('PASS:', path, flush=True)
if not PREPARE_ONLY and (not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT')):
    stop('export DEVELOPER_DIR and IOS_SDKROOT first')
W.mkdir(parents=True, exist_ok=True)

# Obtain the exact old/new templates from the diagnostic script that was
# actually run earlier; do not reverse its edits by guessing or broad replace.
try:
    tree = ast.parse(SCISSOR_SCRIPT.read_text())
    templates = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('old', 'new', 'insert', 'anchor'):
                try:
                    templates[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    pass
    old_func, new_func = templates['old'], templates['new']
except (KeyError, SyntaxError, OSError) as exc:
    stop('cannot verify previous scissor patch templates: ' + str(exc))
if SCISSOR_MARK not in new_func or old_func.count('ui_block_region_draw') != 1:
    stop('unexpected previous scissor diagnostic script; nothing modified')
include_insert = '#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n'
include_anchor = '#include <assert.h>\n'
actual_region = REGION.read_text()
backup_region = REGION_BAK.read_text()
if SCISSOR_MARK not in actual_region:
    stop('scissor marker absent; source state unknown. Do not overwrite region source.')
if backup_region.count(old_func) != 1 or backup_region.count(include_anchor) != 1:
    stop('popup source backup does not match known source pattern')
expected_region = backup_region.replace(include_anchor, include_anchor + include_insert, 1).replace(old_func, new_func, 1)
if actual_region != expected_region:
    stop('interface_regions.c has other edits since scissor test; refusing to restore backup')
print('PASS: previous scissor test is exactly reversible', flush=True)

widget_text = WIDGETS.read_text()
header = '#include <assert.h>\n'
if MARK in widget_text:
    stop('popup width diagnostic is already in interface_widgets.c; no files changed')
if WIDGETS_BAK.exists():
    stop('widget backup exists without test marker; inspect before rerunning: ' + str(WIDGETS_BAK))
if widget_text.count(header) != 1:
    stop('unexpected widgets include layout')
start = widget_text.find('static void ui_text_clip_left(')
end = widget_text.find('\n/**\n * Cut off the text, taking into account the cursor', start)
if start < 0 or end < 0:
    stop('expected ui_text_clip_left boundaries missing')
part = widget_text[start:end]
needle = '''\t\tif (but->strwidth < 10) break;
\t}

\tif (fstyle->kerning == 1) {'''
if part.count(needle) != 1 or 'but->ofs = 0;' not in part or 'UI_BLOCK_LOOP' not in widget_text:
    stop('unknown ui_text_clip_left structure; no files changed')
inject = '''\t\tif (but->strwidth < 10) break;
\t}

#ifdef WITH_IOS
\t/* Blender3GS iOS6 POPUP TEXT WIDTH A/B TEST.
\t * Capture how many characters the UI discards BEFORE BLF_draw(), then
\t * temporarily draw the complete source label in popup menu buttons only.
\t * This is a controlled diagnostic, not the final UI-width fix. */
\tif ((but->block->flag & UI_BLOCK_LOOP) && (but->type == BUT)) {
\t\tstatic int popup_width_log_count = 0;
\t\tconst int clipped_ofs = but->ofs;
\t\tconst float full_width = BLF_width(fstyle->uifont_id, but->drawstr);
\t\tif (popup_width_log_count < 48) {
\t\t\tsyslog(LOG_WARNING,
\t\t\t       "Blender3GS POPUP WIDTH: label='%.70s' rect=(%d,%d)-(%d,%d) "
\t\t\t       "available=%d full_width=%.1f clipped_width=%.1f ofs=%d "
\t\t\t       "remaining='%.70s' font_pt=%d icon=%d",
\t\t\t       but->drawstr, rect->xmin, rect->ymin, rect->xmax, rect->ymax,
\t\t\t       okwidth, (double)full_width, (double)but->strwidth,
\t\t\t       clipped_ofs, but->drawstr + clipped_ofs,
\t\t\t       (int)fstyle->points, (int)((but->flag & UI_HAS_ICON) != 0));
\t\t\tpopup_width_log_count++;
\t\t}
\t\tbut->ofs = 0;
\t\tbut->strwidth = full_width;
\t}
#endif

\tif (fstyle->kerning == 1) {'''
new_part = part.replace(needle, inject, 1)
new_widgets = widget_text.replace(header, header + include_insert, 1)
new_widgets = new_widgets[:new_widgets.find('static void ui_text_clip_left(')] + new_part + new_widgets[new_widgets.find('\n/**\n * Cut off the text, taking into account the cursor', new_widgets.find('static void ui_text_clip_left(')):]
if new_widgets.count(MARK) != 1:
    stop('unexpected widget patch marker count; no files changed')

print('\n=== 2. RESTORE GL SCISSOR + INSTRUMENT POPUP TEXT WIDTH ===', flush=True)
shutil.copy2(WIDGETS, WIDGETS_BAK)
WIDGETS.write_text(new_widgets)
REGION.write_text(backup_region)
print('RESTORED:', REGION, '(verified prior backup)', flush=True)
print('PATCHED:', WIDGETS, flush=True)
print('BACKUP:', WIDGETS_BAK, flush=True)
if PREPARE_ONLY:
    print('PASS: prepare-only local source test; no build/IPA attempted', flush=True)
    raise SystemExit(0)

previous = W / 'Blender3GS-python-before-popup-width-armv7'
if not previous.exists():
    shutil.copy2(EXE, previous)
old_hash = digest(EXE)
run('3. REBUILD UI', ['ninja', '-C', B, '-j4', 'bf_editor_interface'], W / 'popup-width-build.log')
run('4. RELINK PYTHON/RNA/ATEXIT', ['python3', LINKER], W / 'popup-width-link.log')
if digest(EXE) == old_hash:
    stop('linked executable did not change; refusing to package a stale IPA')
run('5. VERIFY ARMv7', ['xcrun', 'lipo', '-info', EXE], W / 'popup-width-arch.log')
nm = subprocess.run(['xcrun', 'nm', '-g', str(EXE)], text=True, capture_output=True)
if nm.returncode or not re.search(r'\b[Tt]\s+_PyInit_atexit\b', nm.stdout):
    stop('linked executable missing PyInit_atexit')

print('\n=== 6. CREATE SEPARATE EXPERIMENTAL IPA ===', flush=True)
pkg = PACKAGER.read_text()
old_name = 'Blender3GS-python-cleanui-test.ipa'
if pkg.count(old_name) != 1:
    stop('unexpected clean-ui packager output name')
pkg = pkg.replace(old_name, IPA.name, 1)
for key, val in (('CFBundleVersion', '9'), ('CFBundleShortVersionString', '0.9.0')):
    pattern = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pattern, pkg)) != 1:
        stop('unknown package version assignment: ' + key)
    pkg = re.sub(pattern, lambda m: m.group(1) + repr(val), pkg, count=1)
NEW_PACKAGER.write_text(pkg)
py_compile.compile(str(NEW_PACKAGER), doraise=True)
run('7. PACKAGE', ['python3', NEW_PACKAGER], W / 'popup-width-package.log')
if not IPA.is_file() or not IPA.stat().st_size:
    stop('missing IPA: ' + str(IPA))
with zipfile.ZipFile(IPA) as z:
    bad = z.testzip()
    if bad:
        stop('corrupt IPA member: ' + bad)
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():
        stop('missing bundled executable')
print('\nSUCCESS: POPUP WIDTH EXPERIMENT READY:', IPA, flush=True)
print('Capture Blender3GS POPUP WIDTH syslog lines while opening Add menu.', flush=True)
print('Working Touch-v2 source, build and IPA were not modified.', flush=True)