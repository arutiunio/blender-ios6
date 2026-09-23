#!/usr/bin/env python3
"""Blender3GS UI v12: isolate batched popup label glyphs + icon GL errors.

This is a separate on-device test, not a promise of a complete repair.
Requires the user's completed UI11 Python/Trackpad sources in ~/Downloads.
Only modifies experimental source tree. Preserves Touch-v2 and prior IPAs.
"""
from pathlib import Path
import os, re, sys, shutil, subprocess, hashlib, zipfile, py_compile

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home()/'Downloads')))
SRC = ROOT/'blender-ios6-target'
UI = SRC/'source/blender/editors/interface'
WID = UI/'interface_widgets.c'
ICO = UI/'interface_icons.c'
GHOST = SRC/'intern/ghost/intern/GHOST_WindowIOS.mm'
B = ROOT/'blender-ios6-build-python'
W = ROOT/'blender-ios6-python'
EXE = ROOT/'Blender3GS-python-armv7'
LINKER = ROOT/'blender-link-ios-python-v3.py'
PACK = W/'Blender3GS-package-cleanui.py'
NEW_PACK = W/'Blender3GS-package-ui-v12.py'
IPA = ROOT/'Blender3GS-python-ui-v12-test.ipa'
TAG = 'BLENDER3GS_UI_V12_20260923'
PREP = '--prepare-only' in sys.argv

def stop(s): raise SystemExit('STOP: '+s)
def exact(s,a,b,where):
    n=s.count(a)
    if n != 1: stop(f'{where}: expected 1 anchor, got {n}; nothing written')
    return s.replace(a,b,1)
def run(title, cmd, out):
    print(f'\n=== {title} ===\nCOMMAND:', ' '.join(map(str,cmd)),flush=True)
    with out.open('w') as f: cp=subprocess.run(list(map(str,cmd)), stdout=f,stderr=subprocess.STDOUT)
    if cp.returncode:
        print(out.read_text(errors='replace')[-18000:]);stop(f'{title}: exit={cp.returncode}; {out}')
    print('PASS:',out,flush=True)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

print('=== 1. PREFLIGHT: UI11 + TRACKPAD / EXPERIMENTAL SOURCE ONLY ===',flush=True)
for p in (WID,ICO,GHOST,B/'build.ninja',EXE,LINKER,PACK):
    if not p.is_file() or not p.stat().st_size: stop('missing: '+str(p))
    print('PASS:',p)
if not PREP and not (os.getenv('DEVELOPER_DIR') and os.getenv('IOS_SDKROOT')):
    stop('export DEVELOPER_DIR and IOS_SDKROOT')
w=WID.read_text(); i=ICO.read_text(); g=GHOST.read_text()
if 'BLENDER3GS_UI_V11_20260923' not in w or 'BLENDER3GS_UI_V11_20260923' not in i: stop('UI11 not found; no assumptions about unknown build')
if 'BLENDER3GS_POPUP_TRACKPAD_20260923' not in g: stop('Trackpad build not found')
if TAG in w or TAG in i: stop('v12 already applied; do not run twice')

print('\n=== 2. BOUNDED PER-GLYPH PATH FOR POPUP LABELS ===',flush=True)
# The on-device UI11 metrics show labels and widths are correct; the keyboard
# underlines, drawn with a separate BLF_draw("_"), appear. This A/B switches
# only menu label rendering from a multi-glyph draw to single-glyph draws.
old = '''\tgpuCurrentColor3ubv((unsigned char *)wcol->text);

\tuiStyleFontDrawExt(fstyle, rect, but->drawstr + but->ofs, &font_xofs, &font_yofs);

\tif (but->menu_key != '\\0') {'''
new = '''\tgpuCurrentColor3ubv((unsigned char *)wcol->text);

#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V12_20260923: test a per-glyph render for ONLY the
\t * left-hand popup label. Existing keyboard shortcuts and all ordinary
\t * Blender regions keep their original paths. UI11 confirmed that each
\t * missing label has a real string, offset=0 and a valid measured width.
\t * A standalone underscore glyph is visible on the real device. */
\tif ((but->block->flag & UI_BLOCK_LOOP) && but->dt == UI_EMBOSSP &&
\t    but->drawstr[but->ofs] != '\\0') {
\t\tconst char *s = but->drawstr + but->ofs;
\t\tconst int original_align = fstyle->align;
\t\tfloat advance = 0.0f;
\t\tint n = 0;
\t\tstatic int count = 0;
\t\tuiStyleFontSet(fstyle);
\t\tfstyle->align = UI_STYLE_TEXT_LEFT;
\t\tfont_xofs = 0.0f;
\t\tfont_yofs = 0.0f;
\t\twhile (*s && n < 96) {
\t\t\tchar character[8];
\t\t\tint length = BLI_str_utf8_size(s);
\t\t\trcti single = *rect;
\t\t\tfloat offset_y;
\t\t\tif (length < 1 || length > 4) length = 1;
\t\t\tif (single.xmin + (int)advance >= single.xmax - 1) break;
\t\t\tmemcpy(character, s, (size_t)length);
\t\t\tcharacter[length] = '\\0';
\t\t\tsingle.xmin += (int)advance;
\t\t\tif (n == 0)
\t\t\t\tuiStyleFontDrawExt(fstyle, &single, character, &font_xofs, &font_yofs);
\t\t\telse {
\t\t\t\tfloat dummy_x;
\t\t\t\tuiStyleFontDrawExt(fstyle, &single, character, &dummy_x, &offset_y);
\t\t\t}
\t\t\tadvance += BLF_width(fstyle->uifont_id, character);
\t\t\ts += length;
\t\t\tn++;
\t\t}
\t\tif (count < 12) {
\t\t\tsyslog(LOG_WARNING, "Blender3GS UI12 CHARS: label='%.52s' glyphs=%d width=%.1f rect=%d,%d,%d,%d",
\t\t\t       but->drawstr + but->ofs, n, (double)advance,
\t\t\t       rect->xmin, rect->ymin, rect->xmax, rect->ymax);
\t\t\tcount++;
\t\t}
\t\tfstyle->align = original_align;
\t}
\telse
#endif
\t\tuiStyleFontDrawExt(fstyle, rect, but->drawstr + but->ofs, &font_xofs, &font_yofs);

\tif (but->menu_key != '\\0') {'''
w=exact(w,old,new,'popup glyph draw')

print('\n=== 3. ISOLATE STALE GL ERROR FROM ICON UPLOAD ===',flush=True)
# UI11 checked glGetError only at the end. A preexisting GL_INVALID_OPERATION
# (0x502) could therefore have caused it to delete a successfully uploaded atlas.
old='''\t\t\t\tglGenTextures(1, &icongltex.id);
\t\t\t\tif (icongltex.id) {'''
new='''\t\t\t\t/* BLENDER3GS_UI_V12_20260923: record and drain earlier
\t\t\t\t * errors, otherwise an old 0x502 deletes a valid icon texture. */
\t\t\t\t{
\t\t\t\t\tGLenum stale = GL_NO_ERROR;
\t\t\t\t\tint drained = 0;
\t\t\t\t\twhile (drained < 16 && (stale = glGetError()) != GL_NO_ERROR) {
\t\t\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI12 ICON PREERROR: 0x%x", (unsigned)stale);
\t\t\t\t\t\tdrained++;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tglGenTextures(1, &icongltex.id);
\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI12 ICON GEN: id=%u err=0x%x", (unsigned)icongltex.id, (unsigned)glGetError());
\t\t\t\tif (icongltex.id) {'''
i=exact(i,old,new,'GL error / icon atlas preflight')
old='''\t\t\t\t\tif (upload_error != GL_NO_ERROR) {
\t\t\t\t\t\tglDeleteTextures(1, &icongltex.id);
\t\t\t\t\t\ticongltex.id = 0;
\t\t\t\t\t}
\t\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI11 ICONS: source=%dx%d texture=%dx%d err=0x%x id=%u",'''
new='''\t\t\t\t\tif (upload_error != GL_NO_ERROR) {
\t\t\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI12 ICON UPLOAD ERROR: 0x%x", (unsigned)upload_error);
\t\t\t\t\t\tglDeleteTextures(1, &icongltex.id);
\t\t\t\t\t\ticongltex.id = 0;
\t\t\t\t\t}
\t\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI12 ICONS: source=%dx%d texture=%dx%d err=0x%x id=%u",'''
i=exact(i,old,new,'icon upload stage')

# Validate all transformations before first write.
if TAG not in w or TAG not in i: stop('tag missing after patch')
for p in (WID,ICO):
    back=p.with_name(p.name+'.before-'+TAG)
    if back.exists(): stop('backup exists; do not overwrite: '+str(back))
print('\n=== 4. BACKUP AND WRITE ===',flush=True)
for p in (WID,ICO):
    back=p.with_name(p.name+'.before-'+TAG)
    shutil.copy2(p,back);print('BACKUP:',back)
WID.write_text(w);ICO.write_text(i)
print('PATCHED:',WID,'and',ICO)
if PREP:
    print('PASS: prepare-only transformation; no ARM build and no IPA.')
    raise SystemExit(0)
W.mkdir(exist_ok=True,parents=True)
prev_hash=sha(EXE)
prev_binary=W/'Blender3GS-python-before-ui-v12-armv7'
if not prev_binary.exists():shutil.copy2(EXE,prev_binary)
run('5. BUILD EXPERIMENTAL INTERFACE',['ninja','-C',B,'-j4','bf_editor_interface'], W/'ui-v12-build.log')
run('6. RELINK WITH PYTHON/RNA/ATEXIT',['python3',LINKER], W/'ui-v12-link.log')
if sha(EXE)==prev_hash:stop('binary unchanged; refusing stale IPA')
run('7. CHECK ARMv7',['xcrun','lipo','-info',EXE],W/'ui-v12-arch.log')
if 'armv7' not in (W/'ui-v12-arch.log').read_text():stop('not ARMv7')
print('\n=== 8. PACKAGE SEPARATE IPA ===',flush=True)
pkg=PACK.read_text()
pkg=exact(pkg,'Blender3GS-python-cleanui-test.ipa',IPA.name,'IPA name')
for key,val in (('CFBundleVersion','12'),('CFBundleShortVersionString','0.12.0')):
    pat=r"(info\['"+key+r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat,pkg))!=1:stop('unknown packager version field: '+key)
    pkg=re.sub(pat,lambda m:m.group(1)+repr(val),pkg,count=1)
NEW_PACK.write_text(pkg)
py_compile.compile(str(NEW_PACK),doraise=True)
run('9. PACKAGE',['python3',NEW_PACK],W/'ui-v12-package.log')
if not IPA.is_file() or IPA.stat().st_size<1000000:stop('IPA not created')
with zipfile.ZipFile(IPA) as z:
    err=z.testzip()
    if err:stop('invalid ZIP member: '+err)
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():stop('missing executable')
print('\nSUCCESS: UI12 DEVICE TEST CANDIDATE:',IPA)
print('Diagnostic lines: Blender3GS UI12 CHARS / ICON PREERROR / ICON GEN / ICONS')
print('Working Touch v2 and all old IPAs left unchanged.')