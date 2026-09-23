#!/usr/bin/env python3
"""Blender3GS UI v13: conservative iOS6 GLES2 UI/VRAM candidate.

Apply ONLY to the user's existing UI v12 experimental build on their Mac.
The target source tree is edited with backups; the previously packaged and
installed stable Touch v2 app remains unchanged. Fail closed on unknown state.

Changes:
 - force font and icon draws to sampler unit 0 (native GLES2 state isolation);
 - retry only the first popup glyph once (bounded workaround for cold font draws);
 - cap each BLF alpha atlas page to 512x512 on iOS (256 KiB/page);
 - use Overlap compositing with retained CAEAGLLayer backing (less Blender
   triple-buffer texture caching; retention has its own potential cost).

This is an on-device candidate: NOT a fully validated fix/benchmark.
"""
from pathlib import Path
import os, sys, hashlib, shutil, subprocess, zipfile, re, py_compile

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home()/'Downloads')))
SRC = ROOT / 'blender-ios6-target'
BLF = SRC/'source/blender/blenfont/intern/blf.c'
GLYPH = SRC/'source/blender/blenfont/intern/blf_glyph.c'
WIDGETS = SRC/'source/blender/editors/interface/interface_widgets.c'
ICON = SRC/'source/blender/editors/interface/interface_icons.c'
STYLE = SRC/'source/blender/editors/interface/interface_style.c'
GHOST = SRC/'intern/ghost/intern/GHOST_WindowIOS.mm'
DRAW = SRC/'source/blender/windowmanager/intern/wm_draw.c'
BUILD = ROOT/'blender-ios6-build-python'
WORK = ROOT/'blender-ios6-python'
EXEC = ROOT/'Blender3GS-python-armv7'
LINK = ROOT/'blender-link-ios-python-v3.py'
PACK = WORK/'Blender3GS-package-cleanui.py'
NEW_PACK = WORK/'Blender3GS-package-ui-v13.py'
IPA = ROOT/'Blender3GS-python-ui-v13-test.ipa'
TAG='BLENDER3GS_UI_V13_20260923'
PREP='--prepare-only' in sys.argv

def stop(message): raise SystemExit('STOP: '+message)
def exact(source, old, new, where):
    count=source.count(old)
    if count != 1: stop(f'{where}: expected one exact anchor; found {count}. No files modified.')
    return source.replace(old,new,1)
def run(what, args, log):
    print(f'\n=== {what} ===\nCOMMAND:', ' '.join(map(str,args)),flush=True)
    with log.open('w') as handle:
        result=subprocess.run(list(map(str,args)),stdout=handle,stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(errors='replace')[-20000:])
        stop(f'{what} failed ({result.returncode}): {log}')
    print('PASS:',log)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def first_glyph_patch(text):
    # UI12 uses the same code for every menu item; repeat only the first glyph
    # in the already bounded popup path to test a cold-atlas/first-draw failure.
    a='''\t\t\tif (n == 0)
\t\t\t\tuiStyleFontDrawExt(fstyle, &single, character, &font_xofs, &font_yofs);
\t\t\telse {'''
    b='''\t\t\tif (n == 0) {
\t\t\t\t/* BLENDER3GS_UI_V13_20260923: bounded first-glyph retry;
\t\t\t\t * do not duplicate entire strings or non-popup text. */
\t\t\t\tuiStyleFontDrawExt(fstyle, &single, character, &font_xofs, &font_yofs);
\t\t\t\tuiStyleFontDrawExt(fstyle, &single, character, &font_xofs, &font_yofs);
\t\t\t}
\t\t\telse {'''
    return exact(text,a,b,'UI12 first glyph branch')

print('=== 1. PREFLIGHT EXPERIMENTAL UI12 SOURCE ===')
paths=(BLF,GLYPH,WIDGETS,ICON,STYLE,GHOST,DRAW,BUILD/'build.ninja',EXEC,LINK,PACK)
for p in paths:
    if not p.is_file() or not p.stat().st_size: stop('missing/empty: '+str(p))
    print('PASS:',p)
if not PREP and not (os.getenv('DEVELOPER_DIR') and os.getenv('IOS_SDKROOT')):
    stop('set DEVELOPER_DIR and IOS_SDKROOT')
original={p:p.read_text() for p in (BLF,GLYPH,WIDGETS,ICON,STYLE,GHOST,DRAW)}
if 'BLENDER3GS_UI_V12_20260923' not in original[WIDGETS] or 'BLENDER3GS_UI_V12_20260923' not in original[ICON]:
    stop('UI12 changes absent; do not apply to an unknown source state')
if 'BLENDER3GS_POPUP_TRACKPAD_20260923' not in original[GHOST]:
    stop('trackpad changes absent; do not modify stable build')
if any(TAG in content for content in original.values()): stop('UI13 already applied')

print('\n=== 2. PREPARE IN-MEMORY PATCHES (NO FILES WRITTEN YET) ===')
updates={}
blf=original[BLF]
blf=exact(blf,'\t/* always bind the texture for the first glyph */\n\tfont->tex_bind_state = -1;',
'''#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V13_20260923: Blender's GLES2 shader samples unit 0;
\t * viewport code may have left another texture unit active. Set the
\t * same unit before any font atlas binding/upload. */
\tglActiveTexture(GL_TEXTURE0);
#endif
\t/* always bind the texture for the first glyph */
\tfont->tex_bind_state = -1;''','BLF GLES2 active texture')
updates[BLF]=blf

glyph=original[GLYPH]
glyph=exact(glyph,
'''\tgc->p2_width = blf_next_p2((gc->rem_glyphs * gc->max_glyph_width) + (gc->pad * 2));
\tif (gc->p2_width > font->max_tex_size)''',
'''\tgc->p2_width = blf_next_p2((gc->rem_glyphs * gc->max_glyph_width) + (gc->pad * 2));
#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V13_20260923: smaller alpha atlas pages for UI
\t * fonts, leaving unusually large custom fonts unrestricted. */
\tif (gc->max_glyph_width <= 128.0f && gc->max_glyph_height <= 128.0f && gc->p2_width > 512)
\t\tgc->p2_width = 512;
#endif
\tif (gc->p2_width > font->max_tex_size)''','BLF atlas width cap')
glyph=exact(glyph,
'''\tif (gc->p2_height > font->max_tex_size)
\t\tgc->p2_height = font->max_tex_size;''',
'''#ifdef WITH_IOS
\tif (gc->max_glyph_width <= 128.0f && gc->max_glyph_height <= 128.0f && gc->p2_height > 512)
\t\tgc->p2_height = 512;
#endif
\tif (gc->p2_height > font->max_tex_size)
\t\tgc->p2_height = font->max_tex_size;''','BLF atlas height cap')
updates[GLYPH]=glyph

widget=first_glyph_patch(original[WIDGETS]);updates[WIDGETS]=widget

icon=original[ICON]
icon=exact(icon,
'''\t\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\t\tglPixelStorei(GL_UNPACK_ALIGNMENT, 4);''',
'''\t\t\t\t\t/* BLENDER3GS_UI_V13_20260923: sampler0 is the GPU
\t\t\t\t\t * shader's atlas unit; don't inherit viewport active unit. */
\t\t\t\t\tglActiveTexture(GL_TEXTURE0);
\t\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\t\tglPixelStorei(GL_UNPACK_ALIGNMENT, 4);''','icon texture upload unit')
updates[ICON]=icon

style=original[STYLE]
style=exact(style,
'''\tBLF_position(fs->uifont_id, rect->xmin + xofs, rect->ymin + yofs, 0.0f);

\tif (fs->shadow) {
\t\tBLF_enable(fs->uifont_id, BLF_SHADOW);
\t\tBLF_shadow(fs->uifont_id, fs->shadow, fs->shadowcolor, fs->shadowcolor, fs->shadowcolor, fs->shadowalpha);
\t\tBLF_shadow_offset(fs->uifont_id, fs->shadx, fs->shady);
\t}''',
'''\tBLF_position(fs->uifont_id, rect->xmin + xofs, rect->ymin + yofs, 0.0f);

#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V13_20260923: drop the optional UI text shadow.
\t * A 3/5-pixel BLF shadow expands to 9/25 textured quads per glyph;
\t * on the 3GS plain glyphs are more legible and cheaper to draw. */
\tBLF_disable(fs->uifont_id, BLF_SHADOW);
#else
\tif (fs->shadow) {
\t\tBLF_enable(fs->uifont_id, BLF_SHADOW);
\t\tBLF_shadow(fs->uifont_id, fs->shadow, fs->shadowcolor, fs->shadowcolor, fs->shadowcolor, fs->shadowalpha);
\t\tBLF_shadow_offset(fs->uifont_id, fs->shadx, fs->shady);
\t}
#endif''','iOS UI text shadow overhead')
updates[STYLE]=style

ghost=original[GHOST]
ghost=exact(ghost,
'''[NSNumber numberWithBool:NO],
\t\t\tkEAGLDrawablePropertyRetainedBacking,''',
'''/* BLENDER3GS_UI_V13_20260923: Overlap draws only dirty areas;
\t\t\t * retain presented color pixels between frames. */
\t\t\t[NSNumber numberWithBool:YES],
\t\t\tkEAGLDrawablePropertyRetainedBacking,''','CAEAGLLayer retained backing')
updates[GHOST]=ghost

draw=original[DRAW]
draw=exact(draw,
'''static int wm_automatic_draw_method(wmWindow *win)
{''',
'''static int wm_automatic_draw_method(wmWindow *win)
{
#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V13_20260923: avoid Blender's triple-buffer
\t * cached textures on a 256 MB device. The CAEAGLLayer above now
\t * retains backing so partial redraw has stable previous pixels. */
\treturn USER_DRAW_OVERLAP;
#endif''','iOS compositor method')
updates[DRAW]=draw

for p,s in updates.items():
    if TAG not in s or s==original[p]: stop('bad transformation: '+str(p))
    if p.with_name(p.name+'.before-'+TAG).exists(): stop('backup exists: '+str(p))
print('PASS: all 7 source transformations verified in memory')

print('\n=== 3. BACKUP THEN PATCH EXPERIMENTAL SOURCES ===')
for p in updates:
    back=p.with_name(p.name+'.before-'+TAG)
    shutil.copy2(p,back)
    print('BACKUP:',back)
for p,s in updates.items():
    p.write_text(s)
    print('PATCHED:',p)
if PREP:
    print('SUCCESS: PREPARE-ONLY PATCH; no ARM compilation or IPA')
    raise SystemExit(0)
WORK.mkdir(exist_ok=True,parents=True)
old_hash=sha(EXEC)
prev=WORK/'Blender3GS-python-before-ui-v13-armv7'
if not prev.exists(): shutil.copy2(EXEC,prev)

print('\n=== 4. DISCOVER ACTUAL NINJA TARGETS ===')
found=subprocess.run(['ninja','-C',str(BUILD),'-t','targets','all'],capture_output=True,text=True)
if found.returncode:stop('ninja target discovery failed: '+found.stderr[-3000:])
known=found.stdout
wanted=[('bf_blenfont','libbf_blenfont.a'),('bf_editor_interface','libbf_editor_interface.a'),('bf_intern_ghost','libbf_intern_ghost.a'),('bf_windowmanager','libbf_windowmanager.a')]
selected=[]
for preferred,archive in wanted:
    hits=[line.split(':',1)[0] for line in known.splitlines() if line.split(':',1)[0].endswith('/'+archive) or line.split(':',1)[0]==archive]
    if hits: selected.append(hits[0])
    elif re.search(r'^'+re.escape(preferred)+r':',known,re.M):selected.append(preferred)
    else:stop('cannot resolve ninja target '+preferred+' or '+archive+'; check actual build.ninja')
print('TARGETS:',', '.join(selected))
run('5. REBUILD CHANGED ARCHIVES',['ninja','-C',BUILD,'-j4',*selected],WORK/'ui-v13-build.log')
run('6. RELINK WITH EXISTING PYTHON/RNA/ATEXIT',['python3',LINK],WORK/'ui-v13-link.log')
if old_hash==sha(EXEC):stop('linked executable unchanged; refusing to package stale build')
run('7. VERIFY ARMv7',['xcrun','lipo','-info',EXEC],WORK/'ui-v13-arch.log')
if 'armv7' not in (WORK/'ui-v13-arch.log').read_text():stop('binary is not armv7')

print('\n=== 8. PACKAGE NEW EXPERIMENTAL IPA ===')
pkg=PACK.read_text()
pkg=exact(pkg,'Blender3GS-python-cleanui-test.ipa',IPA.name,'IPA destination')
for key,value in (('CFBundleVersion','13'),('CFBundleShortVersionString','0.13.0')):
    pat=r"(info\['"+key+r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat,pkg))!=1: stop('unknown packager version field '+key)
    pkg=re.sub(pat, lambda m:m.group(1)+repr(value),pkg,count=1)
NEW_PACK.write_text(pkg)
py_compile.compile(str(NEW_PACK),doraise=True)
run('9. PACKAGE',['python3',NEW_PACK],WORK/'ui-v13-package.log')
if not IPA.is_file() or IPA.stat().st_size<1000000:stop('IPA not created')
with zipfile.ZipFile(IPA) as z:
    if z.testzip():stop('IPA ZIP invalid')
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():stop('missing ARM app executable')
print('\nSUCCESS: UI13 DEVICE TEST CANDIDATE:',IPA)
print('Stable Touch-v2 IPA/installed app unchanged; target source edits have backups.')
print('Retained backing may cost additional memory; compare on-device performance.')