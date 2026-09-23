#!/usr/bin/env python3
"""Blender3GS UI17: Properties text/headers + instrument registered native panels.

Apply on the user's currently built UI16 experimental source tree on the Mac.
Uses the UI12 on-device result (one BLF_draw per glyph restores popup text),
but extends that known technique to uiStyleFontDrawExt, the shared normal
widget and panel-title text path. Keep Python/RNA/ATEXIT/Trackpad/UI16 layout.
No GL function pointers added. No existing IPA overwritten. Fail closed.

This is a device candidate, not a claimed complete fix or measured performance
improvement. Once the GLES glyph root cause is repaired, remove this fallback.
"""
from pathlib import Path
import os, sys, re, hashlib, shutil, subprocess, zipfile, py_compile

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home() / 'Downloads')))
SRC = ROOT / 'blender-ios6-target'
STYLE = SRC/'source/blender/editors/interface/interface_style.c'
BUTTONS = SRC/'source/blender/editors/space_buttons/space_buttons.c'
HEADER = SRC/'source/blender/editors/space_buttons/buttons_header.c'
WM = SRC/'source/blender/windowmanager/intern/wm_files.c'
WIDGETS = SRC/'source/blender/editors/interface/interface_widgets.c'
BUILD = ROOT/'blender-ios6-build-python'
WORK = ROOT/'blender-ios6-python'
EXE = ROOT/'Blender3GS-python-armv7'
LINK = ROOT/'blender-link-ios-python-v3.py'
PACK16 = WORK/'Blender3GS-package-ui-v16.py'
PACK17 = WORK/'Blender3GS-package-ui-v17.py'
IPA = ROOT/'Blender3GS-python-ui-v17-properties-text.ipa'
TAG = 'BLENDER3GS_UI17_PROPERTIES_TEXT_20260923'
PREP = '--prepare-only' in sys.argv

def stop(msg): raise SystemExit('STOP: ' + msg)
def once(s, before, after, label):
    n = s.count(before)
    if n != 1: stop('%s: required exact anchor occurred %d times; no files modified' % (label, n))
    return s.replace(before, after, 1)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def run(name, argv, log):
    print('\n=== '+name+' ===\nCOMMAND: '+' '.join(map(str,argv)), flush=True)
    with log.open('w') as out:
        r = subprocess.run(list(map(str, argv)), stdout=out, stderr=subprocess.STDOUT)
    if r.returncode:
        print(log.read_text(errors='replace')[-20000:])
        stop('%s: exit=%d; see %s' % (name, r.returncode, log))
    print('PASS:',log,flush=True)

print('=== 1. PREFLIGHT UI16 EXPERIMENTAL SOURCES ===', flush=True)
for p in (STYLE,BUTTONS,HEADER,WM,WIDGETS,BUILD/'build.ninja',EXE,LINK,PACK16):
    if not p.is_file() or not p.stat().st_size: stop('missing/empty: '+str(p))
    print('PASS:',p)
if not PREP and not(os.getenv('DEVELOPER_DIR') and os.getenv('IOS_SDKROOT')):
    stop('set DEVELOPER_DIR and IOS_SDKROOT before building')
style=STYLE.read_text(); buttons=BUTTONS.read_text(); header=HEADER.read_text()
if 'BLENDER3GS_UI_V13_20260923' not in style: stop('UI13 text path missing')
if 'BLENDER3GS_UI16_REAL_PROPERTIES_20260923' not in header: stop('UI16 text-tab source missing')
if 'BLENDER3GS_UI16_REAL_PROPERTIES_20260923' not in WM.read_text(): stop('UI16 screen geometry source missing')
if 'BLENDER3GS_UI_V12_20260923' not in WIDGETS.read_text(): stop('known working popup glyph fallback missing')
if TAG in style or TAG in buttons: stop('UI17 patch already applied')
if IPA.exists() or PACK17.exists(): stop('UI17 IPA/packager already exists; never overwrite')

print('\n=== 2. PREPARE TEXT RENDER FIX IN MEMORY ===', flush=True)
# Keep UTF-8 glyph boundaries. UI12 verified per-glyph drawing on the 3GS,
# but it affected only transient popup entries. uiStyleFontDrawExt is also
# used for native Properties buttons, context-tab text and panel titles.
style=once(style, '#include "BLI_string.h"\n',
    '#include "BLI_string.h"\n#ifdef WITH_IOS\n#include "BLI_string_utf8.h"\n#endif\n',
    'UTF-8 glyph helper include')
old='''\tBLF_draw(fs->uifont_id, str, BLF_DRAW_STR_DUMMY_MAX);
\tBLF_disable(fs->uifont_id, BLF_CLIPPING);'''
new='''#ifdef WITH_IOS
    /* BLENDER3GS_UI17_PROPERTIES_TEXT_20260923: the 3GS GLES bridge loses
     * batches of BLF glyph quads. UI12's isolated per-glyph draw recovered
     * popup labels. Apply the same bounded path to normal widgets and panel
     * headers; preserve baseline/clipping/align/shadow setup above. */
    {
        const char *cursor = str;
        const float y = (float)(rect->ymin + yofs);
        float pen = (float)(rect->xmin + xofs);
        int count = 0;
        while (*cursor && count < 512) {
            int bytes = BLI_str_utf8_size(cursor);
            char glyph[8];
            int i;
            if (bytes < 1 || bytes > 4) bytes = 1;
            /* Never copy through the terminator of malformed UTF-8. */
            for (i = 0; i < bytes && cursor[i] != '\\0'; i++)
                glyph[i] = cursor[i];
            if (!i) break;
            glyph[i] = '\\0';
            BLF_position(fs->uifont_id, pen, y, 0.0f);
            BLF_draw(fs->uifont_id, glyph, (size_t)i);
            pen += BLF_width(fs->uifont_id, glyph);
            cursor += i;
            count++;
        }
        if (*cursor) { /* preserve the rest of unusually long labels */
            BLF_position(fs->uifont_id, pen, y, 0.0f);
            BLF_draw(fs->uifont_id, cursor, BLF_DRAW_STR_DUMMY_MAX);
        }
    }
#else
\tBLF_draw(fs->uifont_id, str, BLF_DRAW_STR_DUMMY_MAX);
#endif
\tBLF_disable(fs->uifont_id, BLF_CLIPPING);'''
style=once(style,old,new,'normal uiStyleFontDrawExt glyph batch')

print('\n=== 3. PREPARE PROPERTIES PANEL DIAGNOSTICS ===', flush=True)
# Log registration counts and real view2d geometry. This distinguishes
# a missing Python Panel registration from a font or stale-scroll bug.
buttons=once(buttons,'#include <stdio.h>\n',
    '#include <stdio.h>\n#ifdef WITH_IOS\n#include <syslog.h>\n#endif\n',
    'space_buttons syslog include')
buttons=once(buttons,
'''\tbuttons_context_compute(C, sbuts);

\tif (sbuts->mainb == BCONTEXT_SCENE)''',
'''\tbuttons_context_compute(C, sbuts);
#ifdef WITH_IOS
    /* BLENDER3GS_UI17_PROPERTIES_TEXT_20260923: report actual native
     * panel registration and visible 2D range, not just SPACE_BUTS type. */
    {
        static int logged = 0;
        if (logged < 12) {
            PanelType *pt;
            int total = 0, mod = 0, render = 0, obj = 0, mat = 0;
            float curw = ar->v2d.cur.xmax - ar->v2d.cur.xmin;
            for (pt = ar->type->paneltypes.first; pt; pt = pt->next) {
                total++;
                if (!strcmp(pt->context, "modifier")) mod++;
                if (!strcmp(pt->context, "render")) render++;
                if (!strcmp(pt->context, "object")) obj++;
                if (!strcmp(pt->context, "material")) mat++;
            }
            syslog(LOG_WARNING,
                   "Blender3GS UI17 PROPERTIES: mainb=%d requested=%d valid=0x%x region=%dx%d curX=%.1f..%.1f curWidth=%.1f panels=%d modifier=%d render=%d object=%d material=%d",
                   sbuts->mainb, sbuts->mainbuser, (unsigned)sbuts->pathflag,
                   ar->winx, ar->winy,
                   (double)ar->v2d.cur.xmin, (double)ar->v2d.cur.xmax,
                   (double)curw, total, mod, render, obj, mat);
            logged++;
        }
    }
#endif

\tif (sbuts->mainb == BCONTEXT_SCENE)''',
    'Properties main draw instrumentation')

pkg=PACK16.read_text()
pkg=once(pkg,'Blender3GS-python-ui-v16-properties.ipa',IPA.name,'UI17 output name')
for key,value in (('CFBundleVersion','17'),('CFBundleShortVersionString','0.17.0')):
    pat=r"(info\['"+key+r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat,pkg))!=1: stop('unknown package version field '+key)
    pkg=re.sub(pat,lambda m:m.group(1)+repr(value),pkg,count=1)
for p,c in ((STYLE,style),(BUTTONS,buttons)):
    if TAG not in c:stop('bad generated patch: '+str(p))
    if p.with_name(p.name+'.before-ios6-ui17').exists():stop('backup already exists: '+str(p))
print('PASS: font path + actual Properties diagnostics + package prepared in memory')

print('\n=== 4. BACKUP AND PATCH EXPERIMENTAL SOURCE ===', flush=True)
for p,c in ((STYLE,style),(BUTTONS,buttons)):
    backup=p.with_name(p.name+'.before-ios6-ui17')
    shutil.copy2(p,backup)
    p.write_text(c)
    print('BACKUP:',backup,'\nPATCHED:',p,flush=True)
if PREP:
    print('\nSUCCESS: UI17 PREPARE ONLY (no ARM compilation/IPA)',flush=True)
    raise SystemExit(0)

WORK.mkdir(parents=True,exist_ok=True)
prev_hash=sha(EXE)
prev=WORK/'Blender3GS-python-before-ui-v17-armv7'
if not prev.exists():
    shutil.copy2(EXE,prev)
    print('BACKUP:',prev)
print('\n=== 5. BUILD + LINK + PACKAGE UI17 ===', flush=True)
run('BUILD font widgets and Properties', ['ninja','-C',BUILD,'-j4','bf_editor_interface','bf_editor_space_buttons'], WORK/'ui-v17-build.log')
run('RELINK Python / RNA / atexit / GLES2 / UI16', ['python3',LINK], WORK/'ui-v17-link.log')
if sha(EXE)==prev_hash: stop('executable hash unchanged; refusing stale IPA')
run('VERIFY ARMv7', ['xcrun','lipo','-info',EXE], WORK/'ui-v17-arch.log')
if 'armv7' not in (WORK/'ui-v17-arch.log').read_text(): stop('unexpected architecture')
PACK17.write_text(pkg)
py_compile.compile(str(PACK17),doraise=True)
run('PACKAGE separate UI17 IPA', ['python3',PACK17], WORK/'ui-v17-package.log')
if not IPA.is_file() or IPA.stat().st_size < 1000000: stop('IPA missing or unexpectedly small')
with zipfile.ZipFile(IPA) as z:
    if z.testzip():stop('IPA ZIP CRC failure')
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():stop('no app executable in IPA')
print('\nSUCCESS: UI17 DEVICE TEST CANDIDATE:',IPA)
print('Expected logs: Blender3GS UI17 PROPERTIES')
print('Previous UI16 IPA and working Touch v2 unchanged.')