#!/usr/bin/env python3
"""UI18: restore Blender 2.64 native icon tabs in existing UI17 mobile Properties.

The UI16 layout patch explicitly replaced every Properties tab icon with an
R/S/W/O/M/D/Mt text label. This is a narrow, testable change to those seven
buttons only; UI17 per-glyph font fix, UI16 area geometry, GLES2, Python,
Trackpad, RNA and atexit are retained. Does not edit Touch-v2 sources/IPA.
"""
from pathlib import Path
import os, sys, re, shutil, subprocess, hashlib, zipfile, py_compile

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home()/'Downloads')))
SRC = ROOT/'blender-ios6-target'
HEADER = SRC/'source/blender/editors/space_buttons/buttons_header.c'
STYLE = SRC/'source/blender/editors/interface/interface_style.c'
ICONS = SRC/'source/blender/editors/interface/interface_icons.c'
WM = SRC/'source/blender/windowmanager/intern/wm_files.c'
BUILD = ROOT/'blender-ios6-build-python'
WORK = ROOT/'blender-ios6-python'
EXE = ROOT/'Blender3GS-python-armv7'
LINK = ROOT/'blender-link-ios-python-v3.py'
PACK17 = WORK/'Blender3GS-package-ui-v17.py'
PACK18 = WORK/'Blender3GS-package-ui-v18.py'
IPA = ROOT/'Blender3GS-python-ui-v18-icon-tabs.ipa'
BACKUP = HEADER.with_name(HEADER.name+'.before-ios6-ui18-icon-tabs')
TAG = 'BLENDER3GS_UI18_NATIVE_ICON_TABS_20260923'
PREP = '--prepare-only' in sys.argv

def stop(msg): raise SystemExit('STOP: '+msg)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(label, cmd, log):
    print('\n=== '+label+' ===\nCOMMAND: '+' '.join(map(str,cmd)),flush=True)
    with log.open('w') as h:
        r=subprocess.run(list(map(str,cmd)),stdout=h,stderr=subprocess.STDOUT)
    if r.returncode:
        print(log.read_text(errors='replace')[-16000:],flush=True)
        stop('%s failed (exit %d): %s' % (label,r.returncode,log))
    print('PASS:',log,flush=True)

print('=== 1. VERIFY CURRENT UI17 EXPERIMENT ===',flush=True)
for p in (HEADER,STYLE,ICONS,WM,BUILD/'build.ninja',EXE,LINK,PACK17):
    if not p.is_file() or not p.stat().st_size:stop('missing/empty: '+str(p))
    print('PASS:',p)
if not PREP and not (os.getenv('DEVELOPER_DIR') and os.getenv('IOS_SDKROOT')):
    stop('export DEVELOPER_DIR and IOS_SDKROOT before building')
if 'BLENDER3GS_UI17_PROPERTIES_TEXT_20260923' not in STYLE.read_text():
    stop('UI17 text fix missing: do not patch unexpected source')
if 'BLENDER3GS_UI16_REAL_PROPERTIES_20260923' not in WM.read_text():
    stop('UI16 mobile screen geometry missing')
if 'BLENDER3GS_UI_V11_20260923' not in ICONS.read_text():
    stop('padded GLES2 icon texture code missing')
original=HEADER.read_text()
if TAG in original or BACKUP.exists() or PACK18.exists() or IPA.exists():
    stop('UI18 already applied or output/backup exists; refusing to overwrite')
start_marker='#define BLENDER3GS_MOBILE_CTX(_ctx, _label, _tip) \\\n'
end_marker='#undef BLENDER3GS_MOBILE_CTX'
if original.count(start_marker)!=1 or original.count(end_marker)!=1:
    stop('cannot identify the exact UI16 mobile tab macro')
a=original.index(start_marker)
b=original.index(end_marker,a)+len(end_marker)
old=original[a:b]
if 'uiDefButS(block, ROW, B_CONTEXT_SWITCH, _label,' not in old or 'uiDefIconButS' in old:
    stop('UI16 text-only tab implementation not present')
expected=[
    ('BCONTEXT_RENDER','"R"','ICON_SCENE'),
    ('BCONTEXT_SCENE','"S"','ICON_SCENE_DATA'),
    ('BCONTEXT_WORLD','"W"','ICON_WORLD'),
    ('BCONTEXT_OBJECT','"O"','ICON_OBJECT_DATA'),
    ('BCONTEXT_MODIFIER','"M"','ICON_MODIFIER'),
    ('BCONTEXT_DATA','"D"','sbuts->dataicon'),
    ('BCONTEXT_MATERIAL','"Mt"','ICON_MATERIAL'),
]
lines=old.splitlines()
button_lines=[line for line in lines if line.lstrip().startswith('BLENDER3GS_MOBILE_CTX(')]
if len(button_lines)!=len(expected):stop('expected exactly seven UI16 mobile tab definitions')
for line,(ctx,label,icon) in zip(button_lines,expected):
    if not re.search(r'BLENDER3GS_MOBILE_CTX\('+ctx+r'\s*,\s*'+re.escape(label)+r'\s*,',line):
        stop('unknown tab order/source: '+ctx+' '+line)

print('\n=== 2. REPLACE TEXT-ONLY TABS WITH NATIVE BLENDER ICON BUTTONS ===',flush=True)
new=r'''/* BLENDER3GS_UI18_NATIVE_ICON_TABS_20260923:
 * UI16 intentionally replaced the icons with letters; restore the real
 * Blender 2.64 icon identifiers without adding an overlay or changing the
 * tab callbacks, screen layout, drawing state, or registered Python panels. */
#define BLENDER3GS_MOBILE_CTX(_ctx, _icon, _tip) \
    if (sbuts->pathflag & (1 << _ctx)) { \
        but = uiDefIconButS(block, ROW, B_CONTEXT_SWITCH, _icon, xco += BUT_UNIT_X, yco, BUT_UNIT_X, UI_UNIT_Y, &(sbuts->mainb), 0.0, (float)_ctx, 0, 0, TIP_(_tip)); \
        uiButClearFlag(but, UI_BUT_UNDO); \
    } (void)0
    BLENDER3GS_MOBILE_CTX(BCONTEXT_RENDER,   ICON_SCENE,       N_("Render settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_SCENE,    ICON_SCENE_DATA,  N_("Scene settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_WORLD,    ICON_WORLD,       N_("World settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_OBJECT,   ICON_OBJECT_DATA, N_("Object settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_MODIFIER, ICON_MODIFIER,    N_("Object modifiers"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_DATA,     sbuts->dataicon,  N_("Object data"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_MATERIAL, ICON_MATERIAL,    N_("Materials"));
#undef BLENDER3GS_MOBILE_CTX'''
# Keep the existing #ifdef WITH_IOS/#else header and original desktop tabs.
updated=original[:a]+new+original[b:]
# The desktop #else branch ALREADY contains a native uiDefIconButS macro.
# Verify exactly one NEW macro, not exactly one macro in the whole file.
icon_anchor = 'uiDefIconButS(block, ROW, B_CONTEXT_SWITCH, _icon,'
if (TAG not in updated or new.count(icon_anchor) != 1 or
        updated.count(icon_anchor) != original.count(icon_anchor) + 1 or
        updated[:a] != original[:a] or updated[a+len(new):] != original[b:]):
    stop('internal replacement verification failed')
if updated.count('#ifdef WITH_IOS')!=original.count('#ifdef WITH_IOS'):
    stop('conditional compilation unexpectedly changed')
pack=PACK17.read_text()
if pack.count('Blender3GS-python-ui-v17-properties-text.ipa')!=1:
    stop('unexpected UI17 packager output filename')
pack=pack.replace('Blender3GS-python-ui-v17-properties-text.ipa',IPA.name,1)
for key,val in (('CFBundleVersion','18'),('CFBundleShortVersionString','0.18.0')):
    pat=r"(info\['"+key+r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat,pack))!=1:stop('unexpected package version field '+key)
    pack=re.sub(pat,lambda m:m.group(1)+repr(val),pack,count=1)
print('PASS: seven icon button definitions; native ROW callbacks and original desktop section preserved')

print('\n=== 3. BACKUP AND PATCH UI17 EXPERIMENTAL HEADER ===',flush=True)
shutil.copy2(HEADER,BACKUP)
HEADER.write_text(updated)
print('BACKUP:',BACKUP,'\nPATCHED:',HEADER,flush=True)
if PREP:
    print('\nSUCCESS: UI18 SOURCE PREPARED ONLY; no ARM compile or IPA')
    raise SystemExit(0)
WORK.mkdir(parents=True,exist_ok=True)
old_hash=sha(EXE)
prev=WORK/'Blender3GS-python-before-ui-v18-armv7'
if not prev.exists():shutil.copy2(EXE,prev)
run('4. COMPILE NATIVE PROPERTIES HEADER',['ninja','-C',BUILD,'-j4','bf_editor_space_buttons'],WORK/'ui-v18-build.log')
run('5. RELINK PYTHON / GLES2 / UI17',['python3',LINK],WORK/'ui-v18-link.log')
if sha(EXE)==old_hash:stop('binary unchanged, refusing to package stale build')
run('6. VERIFY ARMv7',['xcrun','lipo','-info',EXE],WORK/'ui-v18-arch.log')
if 'armv7' not in (WORK/'ui-v18-arch.log').read_text():stop('unexpected architecture')
PACK18.write_text(pack)
py_compile.compile(str(PACK18),doraise=True)
run('7. PACKAGE UI18 IPA',['python3',PACK18],WORK/'ui-v18-package.log')
if not IPA.is_file() or IPA.stat().st_size<1000000:stop('new IPA missing/too small')
with zipfile.ZipFile(IPA) as z:
    if z.testzip():stop('IPA ZIP CRC failure')
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():stop('IPA lacks app executable')
print('\nSUCCESS: UI18 NATIVE ICON TAB CANDIDATE:',IPA)
print('Working Touch-v2 app/IPA, installed UI17, previous files and backups unchanged.')
print('Native icon atlas upload already logged id=1 err=0; actual on-screen drawing still needs device test.')