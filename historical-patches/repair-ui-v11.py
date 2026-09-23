#!/usr/bin/env python3
"""Blender 3GS / iOS 6: bounded popup-font and GLES2 icon-atlas repair candidate.

Run on the user's Mac in ~/Downloads with the existing target sources and build.
Does not edit the working Touch-v2 build/IPA or the virtual-trackpad GHOST.

The previous popup GL-state test logged depth=cull=stencil=0 yet menu labels
were absent; this restores that experiment and changes two narrower paths:
(1) stabilize popup-only font point sizes instead of inheriting block aspect;
(2) use a power-of-two RGBA icon atlas on iOS, avoiding GL DrawPixels.
Additional logging tests text measurement/offsets. On-device verification required.
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

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home() / 'Downloads')))
SRC = ROOT / 'blender-ios6-target'
B = ROOT / 'blender-ios6-build-python'
W = ROOT / 'blender-ios6-python'
UI = SRC / 'source/blender/editors/interface'
REGION = UI / 'interface_regions.c'
REGION_BACK = UI / 'interface_regions.c.before-BLENDER3GS_POPUP_TRACKPAD_20260923'
PREV_SCRIPT = ROOT / 'Blender3GS-repair-popup-trackpad.py'
MAIN = UI / 'interface.c'
ICONS = UI / 'interface_icons.c'
WIDGETS = UI / 'interface_widgets.c'
GHOST = SRC / 'intern/ghost/intern/GHOST_WindowIOS.mm'
EXE = ROOT / 'Blender3GS-python-armv7'
LINKER = ROOT / 'blender-link-ios-python-v3.py'
PACKAGER = W / 'Blender3GS-package-cleanui.py'
NEW_PACKAGER = W / 'Blender3GS-package-ui-v11.py'
IPA = ROOT / 'Blender3GS-python-ui-v11-test.ipa'
TAG = 'BLENDER3GS_UI_V11_20260923'
PREPARE_ONLY = '--prepare-only' in sys.argv


def stop(s):
    raise SystemExit('STOP: ' + s)


def section(s):
    print('\n=== ' + s + ' ===', flush=True)


def exact(src, old, new, label):
    n = src.count(old)
    if n != 1:
        stop('%s: expected one match; found %d (no files modified)' % (label, n))
    return src.replace(old, new, 1)


def hash_of(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(label, argv, logfile):
    section(label)
    print('COMMAND:', ' '.join(map(str, argv)), flush=True)
    with logfile.open('w') as out:
        ret = subprocess.run([str(x) for x in argv], stdout=out, stderr=subprocess.STDOUT)
    if ret.returncode:
        print(logfile.read_text(errors='replace')[-20000:], flush=True)
        stop('command exit=%d; see %s' % (ret.returncode, logfile))
    print('PASS:', logfile, flush=True)


def get_previous_templates(path):
    vals = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            k = node.targets[0].id
            if k in {'old_region', 'new_region'}:
                try:
                    vals[k] = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    pass
    if set(vals) != {'old_region', 'new_region'}:
        stop('could not read exact previous popup patch templates')
    return vals


section('1. PREFLIGHT: EXISTING PYTHON/TRACKPAD PROJECT')
need = (REGION, REGION_BACK, PREV_SCRIPT, MAIN, ICONS, WIDGETS, GHOST,
        B / 'build.ninja', EXE, LINKER, PACKAGER)
for p in need:
    if not p.is_file() or p.stat().st_size == 0:
        stop('missing/empty: %s' % p)
    print('PASS:', p)
if not PREPARE_ONLY and not (os.environ.get('DEVELOPER_DIR') and os.environ.get('IOS_SDKROOT')):
    stop('export DEVELOPER_DIR and IOS_SDKROOT first')
if 'BLENDER3GS_POPUP_TRACKPAD_20260923' not in GHOST.read_text():
    stop('expected Trackpad GHOST not found; do not overwrite gesture controls')
for p in (MAIN, ICONS, WIDGETS):
    if TAG in p.read_text():
        stop('v11 already applied in %s; do not apply twice' % p)
if 'Blender3GS iOS6 POPUP TEXT WIDTH A/B TEST' in WIDGETS.read_text():
    stop('old popup-width diagnostic still present: restore it first')

section('2. VERIFY EXACT ROLLBACK OF INEFFECTIVE POPUP GL-STATE EXPERIMENT')
tpl = get_previous_templates(PREV_SCRIPT)
orig_region = REGION_BACK.read_text()
current_region = REGION.read_text()
if orig_region.count(tpl['old_region']) != 1 or 'BLENDER3GS_POPUP_TRACKPAD_20260923' in orig_region:
    stop('popup backup has an unexpected state')
expected_region = orig_region.replace('#include <assert.h>\n',
                                      '#include <assert.h>\n#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n', 1)
expected_region = expected_region.replace(tpl['old_region'], tpl['new_region'], 1)
if current_region != expected_region:
    stop('popup file does not EXACTLY match last patch; refuse unsafe rollback')
print('PASS: last GL-state test can be restored byte-for-byte')

section('3. POPUP FONTS: STABLE PHYSICAL SIZE + BOUNDED DIAGNOSTIC')
main = MAIN.read_text()
main = exact(main, '#include <stddef.h>  /* offsetof() */\n',
    '#include <stddef.h>  /* offsetof() */\n#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n', 'interface.c header')
old_main = '''\tui_fontscale(&style.paneltitle.points, block->aspect);
\tui_fontscale(&style.grouplabel.points, block->aspect);
\tui_fontscale(&style.widgetlabel.points, block->aspect);
\tui_fontscale(&style.widget.points, block->aspect);'''
new_main = '''\tui_fontscale(&style.paneltitle.points, block->aspect);
\tui_fontscale(&style.grouplabel.points, block->aspect);
\tui_fontscale(&style.widgetlabel.points, block->aspect);
\tui_fontscale(&style.widget.points, block->aspect);
#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V11_20260923: A converted popup is already in pixel
\t * coordinates. The inherited block aspect may otherwise make 11pt
\t * labels enormously large compared with its 20px rows. Local style
\t * copy only: regular regions, widgets and saved UI settings unchanged. */
\tif (block->flag & UI_BLOCK_LOOP) {
\t\tstatic int popup_font_count = 0;
\t\tif (popup_font_count < 10) {
\t\t\tsyslog(LOG_WARNING, "Blender3GS UI11 FONT: aspect=%.4f dpi=%d before=%d scaled=%d fixed=11 region=%dx%d",
\t\t\t       (double)block->aspect, (int)U.dpi, (int)UI_GetStyle()->widget.points,
\t\t\t       (int)style.widget.points, ar->winx, ar->winy);
\t\t\tpopup_font_count++;
\t\t}
\t\tstyle.widget.points = 11;
\t\tstyle.widgetlabel.points = 11;
\t\tstyle.grouplabel.points = 11;
\t\tstyle.paneltitle.points = 12;
\t}
#endif'''
main = exact(main, old_main, new_main, 'popup font scale')

section('4. MENU TEXT: LOG MEASUREMENT, PRESERVE FULL LABEL WHEN IT FITS')
w = WIDGETS.read_text()
w = exact(w, '#include <assert.h>\n',
    '#include <assert.h>\n#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n', 'widget include')
old_w = '''\telse if ((but->block->flag & UI_BLOCK_LOOP) && (but->type == BUT)) {
\t\tui_text_clip_left(fstyle, but, rect);
\t}'''
new_w = '''\telse if ((but->block->flag & UI_BLOCK_LOOP) && (but->type == BUT)) {
#ifdef WITH_IOS
\t\t/* BLENDER3GS_UI_V11_20260923: record font metrics at the actual
\t\t * draw site, not during RNA/menu construction. Do not truncate a
\t\t * label that physically fits in the popup button. */
\t\tconst int available = BLI_rcti_size_x(rect) - 10 -
\t\t                      ((but->flag & UI_HAS_ICON) ? UI_DPI_ICON_SIZE : 0);
\t\tfloat measured;
\t\tstatic int text_log_count = 0;
\t\tuiStyleFontSet(fstyle);
\t\tmeasured = BLF_width(fstyle->uifont_id, but->drawstr);
\t\tif (available > 0 && measured >= 0.0f && measured <= (float)available) {
\t\t\tbut->ofs = 0;
\t\t\tbut->strwidth = measured;
\t\t}
\t\telse {
\t\t\tui_text_clip_left(fstyle, but, rect);
\t\t}
\t\tbut->flag |= UI_TEXT_LEFT;
\t\tif (text_log_count < 24) {
\t\t\tsyslog(LOG_WARNING,
\t\t\t       "Blender3GS UI11 TEXT: label='%.55s' points=%d available=%d measured=%.1f offset=%d final_width=%.1f rect=%d,%d,%d,%d",
\t\t\t       but->drawstr, (int)fstyle->points, available, (double)measured,
\t\t\t       (int)but->ofs, (double)but->strwidth,
\t\t\t       rect->xmin, rect->ymin, rect->xmax, rect->ymax);
\t\t\ttext_log_count++;
\t\t}
#else
\t\tui_text_clip_left(fstyle, but, rect);
#endif
\t}'''
w = exact(w, old_w, new_w, 'popup-only text measurement')

section('5. ICONS: USE A POWER-OF-TWO ATLAS ON IOS GLES2')
i = ICONS.read_text()
old_i = '''\t\t/* we only use a texture for cards with non-power of two */
\t\tif (GPU_non_power_of_two_support()) {
\t\t\tglGenTextures(1, &icongltex.id);

\t\t\tif (icongltex.id) {
\t\t\t\ticongltex.w = bbuf->x;
\t\t\t\ticongltex.h = bbuf->y;
\t\t\t\ticongltex.invw = 1.0f / bbuf->x;
\t\t\t\ticongltex.invh = 1.0f / bbuf->y;

\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\tglTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, bbuf->x, bbuf->y, 0, GL_RGBA, GL_UNSIGNED_BYTE, bbuf->rect);
\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
\t\t\t\tglBindTexture(GL_TEXTURE_2D, 0);

\t\t\t\tif (glGetError() == GL_OUT_OF_MEMORY) {
\t\t\t\t\tglDeleteTextures(1, &icongltex.id);
\t\t\t\t\ticongltex.id = 0;
\t\t\t\t}
\t\t\t}
\t\t}'''
new_i = '''\t\t/* BLENDER3GS_UI_V11_20260923: the original 600x640 NPOT icon
\t\t * sheet can fall back to glDrawPixels on GLES. Force a padded
\t\t * texture on iOS. Other platforms keep Blender's original path. */
#ifdef WITH_IOS
\t\t{
\t\t\tint aw = 1, ah = 1, row;
\t\t\tunsigned int *padded;
\t\t\tGLenum upload_error;
\t\t\twhile (aw < bbuf->x) aw *= 2;
\t\t\twhile (ah < bbuf->y) ah *= 2;
\t\t\tpadded = (unsigned int *)calloc((size_t)aw * (size_t)ah, sizeof(unsigned int));
\t\t\tif (padded) {
\t\t\t\tfor (row = 0; row < bbuf->y; ++row)
\t\t\t\t\tmemcpy(padded + (size_t)row * aw,
\t\t\t\t\t       bbuf->rect + (size_t)row * bbuf->x,
\t\t\t\t\t       (size_t)bbuf->x * sizeof(unsigned int));
\t\t\t\tglGenTextures(1, &icongltex.id);
\t\t\t\tif (icongltex.id) {
\t\t\t\t\ticongltex.w = aw;
\t\t\t\t\ticongltex.h = ah;
\t\t\t\t\ticongltex.invw = 1.0f / (float)aw;
\t\t\t\t\ticongltex.invh = 1.0f / (float)ah;
\t\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\t\tglPixelStorei(GL_UNPACK_ALIGNMENT, 4);
\t\t\t\t\tglTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, aw, ah, 0,
\t\t\t\t\t             GL_RGBA, GL_UNSIGNED_BYTE, padded);
\t\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
\t\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
\t\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
\t\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
\t\t\t\t\tupload_error = glGetError();
\t\t\t\t\tglBindTexture(GL_TEXTURE_2D, 0);
\t\t\t\t\tif (upload_error != GL_NO_ERROR) {
\t\t\t\t\t\tglDeleteTextures(1, &icongltex.id);
\t\t\t\t\t\ticongltex.id = 0;
\t\t\t\t\t}
\t\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI11 ICONS: source=%dx%d texture=%dx%d err=0x%x id=%u",
\t\t\t\t\t       bbuf->x, bbuf->y, aw, ah, (unsigned int)upload_error,
\t\t\t\t\t       (unsigned int)icongltex.id);
\t\t\t\t}
\t\t\t\tfree(padded);
\t\t\t}
\t\t\telse syslog(LOG_WARNING, "Blender3GS UI11 ICONS: allocation failed");
\t\t}
#else
\t\tif (GPU_non_power_of_two_support()) {
\t\t\tglGenTextures(1, &icongltex.id);

\t\t\tif (icongltex.id) {
\t\t\t\ticongltex.w = bbuf->x;
\t\t\t\ticongltex.h = bbuf->y;
\t\t\t\ticongltex.invw = 1.0f / bbuf->x;
\t\t\t\ticongltex.invh = 1.0f / bbuf->y;

\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\tglTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, bbuf->x, bbuf->y, 0, GL_RGBA, GL_UNSIGNED_BYTE, bbuf->rect);
\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
\t\t\t\tglTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
\t\t\t\tglBindTexture(GL_TEXTURE_2D, 0);

\t\t\t\tif (glGetError() == GL_OUT_OF_MEMORY) {
\t\t\t\t\tglDeleteTextures(1, &icongltex.id);
\t\t\t\t\ticongltex.id = 0;
\t\t\t\t}
\t\t\t}
\t\t}
#endif'''
i = exact(i, old_i, new_i, 'icon atlas upload')
i = exact(i, '#include <string.h>\n', '#include <string.h>\n#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n', 'icon syslog include')

# Ensure all edits are validated before the first write.
if TAG not in main or TAG not in i or TAG not in w:
    stop('generated patch missing required markers')
if 'BLENDER3GS_POPUP_TRACKPAD_20260923' not in GHOST.read_text():
    stop('unexpected GHOST change')

section('6. BACK UP EVERY EDITED SOURCE BEFORE COMMIT')
updates = {REGION: orig_region, MAIN: main, ICONS: i, WIDGETS: w}
for p in updates:
    backup = p.with_name(p.name + '.before-' + TAG)
    if backup.exists():
        stop('backup already exists: %s' % backup)
for p in updates:
    backup = p.with_name(p.name + '.before-' + TAG)
    shutil.copy2(p, backup)
    print('BACKUP:', backup)
for p, content in updates.items():
    p.write_text(content)
    print('WRITE:', p)

if PREPARE_ONLY:
    print('\nPASS: prepare-only source transformation (no compiling or IPA).')
    raise SystemExit(0)

W.mkdir(parents=True, exist_ok=True)
old_hash = hash_of(EXE)
prev_binary = W / ('Blender3GS-python-before-' + TAG + '-armv7')
if not prev_binary.exists():
    shutil.copy2(EXE, prev_binary)
run('7. BUILD UI LIBRARY', ['ninja', '-C', B, '-j4', 'bf_editor_interface'], W / 'ui-v11-build.log')
run('8. RELINK PYTHON + RNA + ATEXIT', ['python3', LINKER], W / 'ui-v11-link.log')
if old_hash == hash_of(EXE):
    stop('new executable is identical to old; refusing stale package')
run('9. CHECK ARMV7', ['xcrun', 'lipo', '-info', EXE], W / 'ui-v11-arch.log')
if 'armv7' not in (W / 'ui-v11-arch.log').read_text():
    stop('target not armv7')
nm = subprocess.run(['xcrun', 'nm', '-g', str(EXE)], capture_output=True, text=True)
if nm.returncode or not re.search(r'\b[Tt]\s+_PyInit_atexit\b', nm.stdout):
    stop('PyInit_atexit missing')

section('10. GENERATE SEPARATE PYTHON IPA PACKAGER')
pkg = PACKAGER.read_text()
pkg = exact(pkg, 'Blender3GS-python-cleanui-test.ipa', IPA.name, 'packager IPA filename')
for key, value in (('CFBundleVersion', '11'), ('CFBundleShortVersionString', '0.11.0')):
    pat = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat, pkg)) != 1:
        stop('unknown packager version field: ' + key)
    pkg = re.sub(pat, lambda m: m.group(1) + repr(value), pkg, count=1)
NEW_PACKAGER.write_text(pkg)
py_compile.compile(str(NEW_PACKAGER), doraise=True)
run('11. PACKAGE TEST IPA', ['python3', NEW_PACKAGER], W / 'ui-v11-package.log')
if not IPA.is_file() or IPA.stat().st_size < 1000000:
    stop('IPA not created or unexpectedly small')
with zipfile.ZipFile(IPA) as z:
    bad = z.testzip()
    if bad:
        stop('corrupt member: ' + bad)
    if not {'Payload/Blender3GS.app/Info.plist', 'Payload/Blender3GS.app/Blender3GS'} <= set(z.namelist()):
        stop('IPA missing executable / Info.plist')
print('\nSUCCESS: UI11 TEST CANDIDATE:', IPA)
print('Trackpad source intact; working Touch v2 untouched.')
print('Check Blender3GS UI11 FONT / TEXT / ICONS in your already running syslog.')
print('On-device screenshot is required before treating this as a fix.')