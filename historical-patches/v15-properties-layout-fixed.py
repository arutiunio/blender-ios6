#!/usr/bin/env python3
"""Blender3GS UI15: replace visible T/N sidebars with real Properties editor.

Patch only the existing Python experiment based on UI14. Do not touch Touch-v2.
This patches C layout after startup.blend is loaded: hide T/N regions, split
View3D to make a genuine SPACE_BUTS area on the right, initialize its context.
The main Blender timeline/header remain. Unknown source/build states fail closed.
"""
from pathlib import Path
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
WM = SRC / 'source/blender/windowmanager/intern/wm_files.c'
BUILD = ROOT / 'blender-ios6-build-python'
WORK = ROOT / 'blender-ios6-python'
EXE = ROOT / 'Blender3GS-python-armv7'
LINK = ROOT / 'blender-link-ios-python-v3.py'
PACK14 = WORK / 'Blender3GS-package-ui-v14.py'
PACK15 = WORK / 'Blender3GS-package-ui-v15.py'
IPA = ROOT / 'Blender3GS-python-ui-v15-properties.ipa'
BACKUP = WM.with_name(WM.name + '.before-ios6-v15-layout')
TAG = 'BLENDER3GS_MOBILE_LAYOUT_V15_20260923'
PREP = '--prepare-only' in sys.argv


def stop(msg):
    raise SystemExit('STOP: ' + msg)


def replace_once(source, old, new, what):
    count = source.count(old)
    if count != 1:
        stop('%s: exact source anchor expected once, found %d; no source changes' % (what, count))
    return source.replace(old, new, 1)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(title, command, log):
    print('\n=== %s ===\nCOMMAND: %s' % (title, ' '.join(map(str, command))), flush=True)
    with log.open('w') as output:
        status = subprocess.run(list(map(str, command)), stdout=output, stderr=subprocess.STDOUT)
    if status.returncode:
        print(log.read_text(errors='replace')[-20000:])
        stop('%s failed: %s' % (title, log))
    print('PASS:', log)


HELPER = r'''#ifdef WITH_IOS
/* BLENDER3GS_MOBILE_LAYOUT_V15_20260923
 * The narrow column in UI14 is View3D's N-panel, NOT the Buttons editor.
 * Likewise the grey left column is the T-shelf. The real SPACE_BUTS area
 * must be created from a screen split, not by resizing those regions.
 * area_split is implemented in screen_edit.c, a linked editor module. */
extern ScrArea *area_split(bScreen *sc, ScrArea *sa, char dir, float fac, int merge);

static void blender3gs_mobile_properties_layout(bContext *C)
{
    wmWindowManager *wm = CTX_wm_manager(C);
    wmWindow *win;
    if (!wm || G.background) return;

    for (win = wm->windows.first; win; win = win->next) {
        bScreen *screen = win->screen;
        ScrArea *view, *area, *left;
        ARegion *tools, *sidebar;
        SpaceButs *sbuts;
        int view_width, existing_buttons = 0;

        /* Avoid changing arbitrary desktop windows, full-screen temporary
         * screens or files with an existing Properties area. */
        if (!screen || screen->temp || screen->full) continue;
        if (win->sizex < 440 || win->sizex > 560 ||
            win->sizey < 280 || win->sizey > 400) continue;

        for (area = screen->areabase.first; area; area = area->next)
            if (area->spacetype == SPACE_BUTS) existing_buttons = 1;
        if (existing_buttons) {
            syslog(LOG_WARNING, "Blender3GS UI15: existing SPACE_BUTS; preserve layout");
            continue;
        }

        view = BKE_screen_find_big_area(screen, SPACE_VIEW3D, 0);
        if (!view || view->spacetype != SPACE_VIEW3D) continue;
        view_width = view->v4->vec.x - view->v1->vec.x;
        if (view_width < 410) {
            syslog(LOG_WARNING, "Blender3GS UI15: View3D too narrow (%d), no split", view_width);
            continue;
        }
        syslog(LOG_WARNING, "Blender3GS UI15 BEFORE: window=%dx%d View3D x=%d..%d",
               win->sizex, win->sizey, view->v1->vec.x, view->v4->vec.x);

        /* T and N are VIEW3D regions. Hide these first so the copied View3D
         * inherits a clean full-width viewport, without destroying them. */
        tools = BKE_area_find_region_type(view, RGN_TYPE_TOOLS);
        sidebar = BKE_area_find_region_type(view, RGN_TYPE_UI);
        if (tools) tools->flag |= RGN_FLAG_HIDDEN;
        if (sidebar) sidebar->flag |= RGN_FLAG_HIDDEN;

        CTX_wm_window_set(C, win);
        CTX_wm_area_set(C, view);
        CTX_wm_region_set(C, NULL);

        /* For 'v' split, new area is LEFT and original becomes RIGHT.
         * This preserves the working 3D View in the new left area. */
        left = area_split(screen, view, 'v', 0.62f, 1);
        if (!left) {
            syslog(LOG_WARNING, "Blender3GS UI15: area_split refused; T/N hidden only");
            ED_area_tag_redraw(view);
            CTX_wm_area_set(C, NULL);
            continue;
        }

        /* Converts actual right-hand ScrArea to the native Properties editor,
         * including proper RGN_TYPE_WINDOW, header, context and panel init. */
        CTX_wm_area_set(C, view);
        ED_area_newspace(C, view, SPACE_BUTS);
        sbuts = (SpaceButs *)view->spacedata.first;
        if (sbuts) {
            sbuts->align = BUT_VERTICAL;
            sbuts->mainb = BCONTEXT_MODIFIER;
            sbuts->mainbuser = BCONTEXT_MODIFIER;
        }

        CTX_wm_region_set(C, NULL);
        CTX_wm_area_set(C, NULL);
        screen->do_refresh = TRUE;
        ED_screen_refresh(wm, win);
        ED_area_tag_redraw(left);
        ED_area_tag_redraw(view);
        syslog(LOG_WARNING, "Blender3GS UI15 AFTER: View3D=%d..%d Properties=%d..%d T=%d N=%d",
               left->v1->vec.x, left->v4->vec.x,
               view->v1->vec.x, view->v4->vec.x,
               !!tools, !!sidebar);
    }
}
#endif
'''

print('=== 1. PREFLIGHT: EXISTING PYTHON UI14 BUILD ===', flush=True)
for p in (WM, BUILD/'build.ninja', EXE, LINK, PACK14,
          SRC/'source/blender/blenfont/intern/blf.c',
          SRC/'source/blender/editors/interface/interface_icons.c'):
    if not p.is_file() or not p.stat().st_size:
        stop('missing/empty file: ' + str(p))
    print('PASS:', p)
if not PREP and not os.environ.get('IOS_SDKROOT'):
    stop('IOS_SDKROOT is not set')
if 'BLENDER3GS_UI_V14_GLEW_NULL_20260923' not in (SRC/'source/blender/blenfont/intern/blf.c').read_text():
    stop('UI14 source marker absent; do not patch unknown version')
if TAG in WM.read_text():
    stop('UI15 already applied; do not split the screen twice')
if BACKUP.exists():
    stop('source backup already exists: '+str(BACKUP))
if IPA.exists():
    stop('new IPA destination already exists; preserve prior package: '+str(IPA))

print('\n=== 2. PREPARE PRECISE C PATCH ===', flush=True)
source = WM.read_text()
source = replace_once(source,
    '#include <errno.h>\n',
    '#include <errno.h>\n#ifdef WITH_IOS\n#include <syslog.h>\n#endif\n',
    'syslog header')
source = replace_once(source,
    'static void write_history(void);',
    'static void write_history(void);\n\n'+HELPER,
    'mobile layout helper')
# Previous v15 anchor depended on the precise comment and blank lines.
# Work within the one startup function, and verify that window matching and
# WM_check(C) precede the target assignment. Nothing is written until all
# transformations and packager validations succeed.
home = list(re.finditer(r'(?m)^int\s+WM_homefile_read\s*\(', source))
following = list(re.finditer(r'(?m)^int\s+WM_homefile_read_exec\s*\(', source))
if len(home) != 1 or len(following) != 1 or following[0].start() <= home[0].start():
    stop('could not uniquely locate WM_homefile_read; no source changes')
start, end = home[0].start(), following[0].start()
function = source[start:end]
assignment = list(re.finditer(r"(?m)^(?P<indent>[ \t]*)G\.main->name\[0\][ \t]*=[ \t]*'\\0';[ \t]*$", function))
if len(assignment) != 1:
    stop('G.main startup assignment not unique in WM_homefile_read; no source changes')
wm_check = list(re.finditer(r'\bWM_check\s*\(\s*C\s*\)\s*;', function))
if len(wm_check) != 1 or wm_check[0].end() > assignment[0].start():
    stop('WM_check(C) not uniquely before startup assignment; no source changes')
if not re.search(r'\bwm_window_match_do\s*\(\s*C\s*,', function[:wm_check[0].start()]):
    stop('startup window matching not found; no source changes')
if len(function[wm_check[0].end():assignment[0].start()]) > 700:
    stop('startup insertion too far from WM_check(C); inspect actual source')
line_indent = assignment[0].group('indent')
injection = ('#ifdef WITH_IOS\n' + line_indent +
             'blender3gs_mobile_properties_layout(C); /* BLENDER3GS_MOBILE_LAYOUT_V15_20260923 */\n' +
             '#endif\n')
function = function[:assignment[0].start()] + injection + function[assignment[0].start():]
source = source[:start] + function + source[end:]
print('PASS: startup-only insertion verified independently of comments/whitespace')

pkg = PACK14.read_text()
pkg = replace_once(pkg, 'Blender3GS-python-ui-v14-test.ipa', IPA.name, 'UI14 IPA output')
for field, value in (('CFBundleVersion', '15'), ('CFBundleShortVersionString', '0.15.0')):
    pattern = r"(info\['" + field + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pattern,pkg)) != 1:
        stop('unexpected UI14 packager version field: '+field)
    pkg = re.sub(pattern, lambda m: m.group(1)+repr(value),pkg,count=1)
if PACK15.exists() and PACK15.read_text()!=pkg:
    stop('existing UI15 package script differs; preserve it')
print('PASS: source and package substitutions verified in memory')

print('\n=== 3. BACKUP THEN PATCH EXPERIMENTAL WINDOW MANAGER ===', flush=True)
shutil.copy2(WM, BACKUP)
WM.write_text(source)
print('BACKUP:', BACKUP)
print('PATCHED:', WM)
if PREP:
    print('SUCCESS: UI15 PREPARE-ONLY; no ARM compilation or IPA')
    raise SystemExit(0)

WORK.mkdir(parents=True, exist_ok=True)
old_hash = sha(EXE)
previous = WORK/'Blender3GS-python-before-ui-v15-armv7'
if not previous.exists():
    shutil.copy2(EXE, previous)

run('4. BUILD WINDOW MANAGER', ['ninja','-C',BUILD,'-j4','bf_windowmanager'], WORK/'ui-v15-build.log')
run('5. RELINK EXISTING UI14+PYTHON+RNA+ATEXIT', ['python3', LINK], WORK/'ui-v15-link.log')
if sha(EXE) == old_hash:
    stop('linked executable unchanged; will not package stale IPA')
run('6. VERIFY ARMv7', ['xcrun','lipo','-info',EXE], WORK/'ui-v15-arch.log')
if 'armv7' not in (WORK/'ui-v15-arch.log').read_text():
    stop('linked executable is not ARMv7')
PACK15.write_text(pkg)
py_compile.compile(str(PACK15),doraise=True)
run('7. PACKAGE SEPARATE UI15 IPA', ['python3',PACK15],WORK/'ui-v15-package.log')
if not IPA.is_file() or IPA.stat().st_size < 1000000:
    stop('expected new IPA is missing or too small')
with zipfile.ZipFile(IPA) as z:
    if z.testzip():stop('IPA ZIP integrity check failed')
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():
        stop('IPA has no Blender3GS executable')
print('\nSUCCESS: UI15 MOBILE PROPERTIES TEST IPA:', IPA)
print('Log markers: Blender3GS UI15 BEFORE / AFTER')
print('Working Touch-v2, UI14 IPA and previous backups preserved.')