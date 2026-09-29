#!/usr/bin/env python3
"""UI37: faster first *real* Blender frame with incremental Python UI registration.

Source-matched to UI36 on the user's Mac.  Full modules are registered on the
Blender main thread after the first draw, never a Python worker thread.
Experiments with CPU icon buffers instead of the GL4ES texture atlas to isolate
white squares.  Separate IPA and backups; original Touch v2 remains unchanged.
"""
import argparse
import ast
import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

TAG = 'BLENDER3GS_UI37_STAGE_REAL_UI_ICON_BUFFER_20260924'
UI36_WM = '125c11ba4048c01e7a998338c2aaebf68c86623a64f3d26312fa79ccdf51aa6f'
UI24_ICONS = 'e41f57499d0c677b19541b4da6726b5035a20ec4d0c104d54dc2472d28e85adc'
KNOWN_PAYLOAD = 'Blender3GS_UI36_known_good_scripts.zip'
IPA = 'Blender3GS-python-ui-v37-staged-full-ui-buffer-icons.ipa'
WM = 'source/blender/windowmanager/intern/wm.c'
ICONS = 'source/blender/editors/interface/interface_icons.c'
UI = 'scripts/startup/bl_ui/__init__.py'
OPS = 'scripts/startup/bl_operators/__init__.py'
INITIAL_UI = (
    'properties_animviz','properties_data_modifier','properties_render',
    'properties_scene','properties_world','properties_object','properties_data_mesh',
    'properties_data_camera','properties_data_lamp','properties_data_empty',
    'properties_material','properties_texture','properties_object_constraint',
    'space_info','space_view3d','space_view3d_toolbar','space_outliner',
)
INITIAL_OPS = ('view3d','object','wm','mesh','anim')

def stop(s): raise SystemExit('STOP: '+str(s))
def sha(data): return hashlib.sha256(data).hexdigest()
def sha_path(p): return sha(p.read_bytes())
def once(s,old,new,label):
    if s.count(old)!=1: stop('%s: expected exactly one anchor, found %d'%(label,s.count(old)))
    return s.replace(old,new,1)

def module_tuple(src):
    t=ast.parse(src)
    for node in t.body:
        if isinstance(node,ast.Assign) and any(isinstance(n,ast.Name) and n.id=='_modules' for n in node.targets):
            return tuple(ast.literal_eval(node.value))
    stop('_modules list absent')

def staged_init(src, initial, label):
    allnames=module_tuple(src)
    if len(allnames)<15 or not all(name in allnames for name in initial):
        stop(label+' missing expected modules')
    old=('__import__(name=__name__, fromlist=_modules)\n'
         '_namespace = globals()\n'
         '_modules_loaded = {name: _namespace[name] for name in _modules}\n'
         'del _namespace')
    text=('''# BLENDER3GS_UI37_STAGE_REAL_UI_ICON_BUFFER_20260924
# Import primary controls now, register the full original remainder on WM thread
# after the first genuine Blender frame; never leave missing panels indefinitely.
_ui37_initial = %r
_ui37_deferred = [name for name in _modules if name not in _ui37_initial]
_ui37_failures = []
__import__(name=__name__, fromlist=_ui37_initial)
_namespace = globals()
_modules_loaded = {name: _namespace[name] for name in _ui37_initial}
del _namespace
''' % (initial,)).rstrip()
    src=once(src,old,text,label+' initial modules')
    # Preserve stock reload behavior: only already loaded modules are reloaded.
    src+='''

# UI37: one module per WM iteration. Module registry and RNA live on Blender's
# main thread; the original modules remain packaged for all tools and reloads.
def _ui37_step():
    if not _ui37_deferred:
        if _ui37_failures:
            raise RuntimeError("UI37 deferred modules failed: %r" % _ui37_failures)
        return 0
    name = _ui37_deferred.pop(0)
    try:
        package = __import__(name=__name__, fromlist=(name,))
        mod = getattr(package, name)
        _modules_loaded[name] = mod
        # register_module raises when a helper module defines no classes;
        # skip only that legitimate case. It registers the *unregistered*
        # classes of the package and all its submodules, preserving earlier UI.
        if any(bpy.utils._bpy_module_classes(__name__, is_registered=False)):
            bpy.utils.register_module(__name__)
    except Exception:
        _ui37_failures.append(name)
        import traceback
        traceback.print_exc()
        # Propagate to BPY_string_exec so the native syslog has rc != 0.
        # Do not retry every frame and risk an endless render stall.
        raise
    return len(_ui37_deferred) + 1
'''
    compile(src,label+'.py','exec')
    return src, len(allnames)-len(initial), len(allnames)

def patch_wm(src, steps):
    if TAG in src or 'BLENDER3GS_UI35_NATIVE_BOOT_20260924' not in src:
        stop('wm.c is not unmodified UI35/UI36 source')
    # ui28_first_frames increments after first real draw; stage from the second.
    anchor='''        if (ui28_first_frames++ < 6) {'''
    addition='''        /* UI37: first complete native frame must reach UIKit before script work.
         * Never import Blender RNA modules from a worker thread. */
        if (ui28_first_frames && ui37_step < UI37_TOTAL_STEPS && blender3gs_ios6_is_active()) {
            double start_ms = ui28_frame_ms();
            int rc = BPY_string_exec(C,
                "(__import__('bl_ui')._ui37_step(), __import__('bl_operators')._ui37_step())");
            ui37_step++;
            if (rc || ui37_step == 1 || ui37_step %% 8 == 0 || ui37_step == UI37_TOTAL_STEPS)
                syslog(LOG_WARNING, "Blender3GS UI37 STAGE: batch=%%u/%%d ms=%%.1f rc=%%d",
                       ui37_step, UI37_TOTAL_STEPS, ui28_frame_ms()-start_ms, rc);
            if (ui37_step %% 4 == 0 || ui37_step == UI37_TOTAL_STEPS) {
                /* Repaint just the right-side editors: retained 3D view stays fast. */
                wmWindow *ui37_win;
                for (ui37_win = ((wmWindowManager *)CTX_wm_manager(C))->windows.first;
                     ui37_win; ui37_win = ui37_win->next) {
                    if (ui37_win->screen) {
                        ScrArea *ui37_area;
                        for (ui37_area = ui37_win->screen->areabase.first; ui37_area;
                             ui37_area = ui37_area->next)
                            if (ui37_area->spacetype == SPACE_BUTS ||
                                ui37_area->spacetype == SPACE_OUTLINER)
                                ED_area_tag_redraw(ui37_area);
                        ui37_win->screen->do_draw = TRUE;
                    }
                }
            }
        }
'''.replace('UI37_TOTAL_STEPS',str(steps)).replace('%%','%')
    src=once(src,anchor,addition+anchor,'WM stage before frame counter')
    anchor='''    unsigned int ui28_first_frames = 0;'''
    src=once(src,anchor,anchor+'\n    unsigned int ui37_step = 0;','WM counter')
    src=once(src,'#include "DNA_windowmanager_types.h"',
             '#include "DNA_windowmanager_types.h"\n#ifdef WITH_IOS\n#include "DNA_space_types.h"\n#endif', 'WM constants')
    return src

def patch_icons(src):
    if TAG in src or 'BLENDER3GS_UI24_INPUT_STARTUP_LIFE_20260924' not in src:
        stop('icon source missing UI24 guard')
    # The old atlas exists but on this GL4ES path occasionally draws opaque
    # white quads.  Diagnostic A/B alternative: stock 16px icons use per-icon
    # CPU buffer pixels, as Blender's existing fallback does. No new renderer.
    anchor='''#ifdef WITH_IOS
		{
			int aw = 1, ah = 1, row;'''
    replacement='''#ifdef WITH_IOS
        /* BLENDER3GS_UI37_STAGE_REAL_UI_ICON_BUFFER_20260924:
         * GL4ES atlas fallback experiment: avoid glTexImage2D 1024x1024 and
         * use the existing ICON_TYPE_BUFFER path.  Costs ~0.8MB CPU memory;
         * may be slower in icon-heavy menus, but leaves viewport redraw alone. */
        syslog(LOG_WARNING, "Blender3GS UI37 ICON: cpu_buffer_no_atlas=1");
        if (0) {
			int aw = 1, ah = 1, row;'''
    return once(src,anchor,replacement,'icon atlas bypass')

def make_pack(src):
    src=once(src,'Blender3GS-python-ui-v36-full-ui.ipa',IPA,'IPA output')
    src=once(src,"info['CFBundleVersion'] = '36'", "info['CFBundleVersion'] = '37'",'version')
    src=once(src,"info['CFBundleShortVersionString'] = '0.36.0'", "info['CFBundleShortVersionString'] = '0.37.0'",'short version')
    target="print('UI36: bl_ui file count:',len(list((app/'2.64/scripts/startup/bl_ui').glob('*.py'))))"
    inject='''# UI37: override ONLY the two package loaders after exact UI36 restoration.
# All 75 other source files are kept byte-for-byte from the known-good build.
ui37_overrides = {
    'scripts/startup/bl_ui/__init__.py': root / 'Blender3GS_UI37_bl_ui.py',
    'scripts/startup/bl_operators/__init__.py': root / 'Blender3GS_UI37_bl_operators.py',
}
for rel, patch in ui37_overrides.items():
    need(patch, 'UI37 staged loader')
    shutil.copy2(patch, app / '2.64' / rel)
    print('UI37: staged Python package:', rel)
print('UI36: bl_ui file count:',len(list((app/'2.64/scripts/startup/bl_ui').glob('*.py'))))'''
    src=once(src,target,inject,'pack script overrides')
    check='''        if _ui36_z.read('Payload/Blender3GS.app/2.64/' + _ui36_entry) != _ui36_scripts.read(_ui36_entry):
            stop('UI36 IPA does not include exact known-good: ' + _ui36_entry)'''
    repl='''        _ui37_override = ui37_overrides.get(_ui36_entry)
        _ui37_expected = _ui37_override.read_bytes() if _ui37_override else _ui36_scripts.read(_ui36_entry)
        if _ui36_z.read('Payload/Blender3GS.app/2.64/' + _ui36_entry) != _ui37_expected:
            stop('UI37 packaged startup mismatch: ' + _ui36_entry)'''
    src=once(src,check,repl,'IPA verification')
    src=once(src,"print('PASS: UI36 IPA full known-good bpy/bl_ui/bl_operators payload byte-matched')",
        "print('PASS: UI37 exact 75 source files + two staged loaders byte-matched')",'verified message')
    compile(src,'Blender3GS-package-ui-v37.py','exec')
    return src

def run(label,argv,log):
    print('=== '+label+' ===',flush=True)
    print('COMMAND: '+' '.join(map(str,argv)),flush=True)
    with log.open('w') as out:
        p=subprocess.run([str(x) for x in argv],stdout=out,stderr=subprocess.STDOUT)
    if p.returncode:
        print(log.read_text(errors='replace')[-16000:],flush=True)
        stop(label+' failed. Log: '+str(log))
    print('PASS:',log,flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.home()/'Downloads')
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--resume',action='store_true')
    a=parser.parse_args()
    if a.resume and a.check_only:stop('--check-only and --resume conflict')
    root=a.root.expanduser().resolve()
    srcroot=root/'blender-ios6-target';work=root/'blender-ios6-python'
    wm=srcroot/WM;icons=srcroot/ICONS
    p36=root/'Blender3GS-package-ui-v36.py';p37=root/'Blender3GS-package-ui-v37.py'
    # v36's packaged file lives in ~/Downloads (not inside the build work dir).
    payload=root/KNOWN_PAYLOAD
    files=(wm,icons,p36,payload,root/'Blender3GS_UI35_Default.png',root/'Blender3GS_UI35_BootLandscape.png')
    for p in files:
        if not p.is_file():stop('missing '+str(p))
    wbackup=wm.with_name(wm.name+'.before-'+TAG)
    ibackup=icons.with_name(icons.name+'.before-'+TAG)
    source_wm=wbackup if a.resume else wm
    source_ic=ibackup if a.resume else icons
    if sha_path(source_wm)!=UI36_WM:stop('WM source is not UI36; actual='+sha_path(source_wm))
    if sha_path(source_ic)!=UI24_ICONS:stop('icons source differs; actual='+sha_path(source_ic))
    with zipfile.ZipFile(payload) as z:
        if z.testzip():stop('UI36 payload corrupted')
        names=z.namelist()
        if len(names)!=77 or UI not in names or OPS not in names:stop('UI36 known-good payload mismatch')
        ui,nu,totu=staged_init(z.read(UI).decode(),INITIAL_UI,'bl_ui')
        ops,no,toto=staged_init(z.read(OPS).decode(),INITIAL_OPS,'bl_operators')
    steps=max(nu,no)
    newwm=patch_wm(source_wm.read_text(),steps)
    newicons=patch_icons(source_ic.read_text())
    newpack=make_pack(p36.read_text())
    outfiles={wm:newwm,icons:newicons,root/'Blender3GS_UI37_bl_ui.py':ui,
              root/'Blender3GS_UI37_bl_operators.py':ops,p37:newpack}
    if a.resume:
        for p,s in outfiles.items():
            if not p.is_file() or p.read_text()!=s:stop('resume mismatch: '+str(p))
    print('PASS: exact UI36 WM + UI24 icon sources; %d UI modules (%d deferred), %d operators (%d deferred), %d WM batches'%
          (totu,nu,toto,no,steps),flush=True)
    if a.check_only:
        print('SUCCESS: CHECK ONLY; no project files modified',flush=True)
        return
    if (root/IPA).exists():stop('UI37 IPA already exists; use --install-only')
    if not a.resume:
        if wbackup.exists() or ibackup.exists() or any(p.exists() for p in (root/'Blender3GS_UI37_bl_ui.py',root/'Blender3GS_UI37_bl_operators.py',p37)):
            stop('UI37 backup or output already exists; avoid overwriting')
        shutil.copy2(wm,wbackup);shutil.copy2(icons,ibackup)
        for p,s in outfiles.items():p.write_text(s)
        print('BACKUP:',wbackup,ibackup,flush=True)
    if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):stop('Xcode variables not set')
    build=root/'blender-ios6-build-python';exe=root/'Blender3GS-python-armv7';link=root/'blender-link-ios-python-v3.py'
    for p in (build/'build.ninja',exe,link):
        if not p.is_file():stop('missing build input '+str(p))
    # Archive package input copies, don't overwrite the known-good UI36 IPA.
    run('COMPILE UI37',['ninja','-C',build,'-j4','bf_windowmanager','bf_editor_interface'],work/'ui-v37-build.log')
    run('RELINK UI37',['python3',link],work/'ui-v37-link.log')
    run('VERIFY ARMV7',['xcrun','lipo','-info',exe],work/'ui-v37-arch.log')
    if 'armv7' not in (work/'ui-v37-arch.log').read_text().lower():stop('output is not ARMv7')
    run('PACKAGE UI37',['python3',p37],work/'ui-v37-package.log')
    ipa=root/IPA
    if not ipa.is_file():stop('missing packaged UI37 IPA')
    with zipfile.ZipFile(ipa) as z:
        if z.testzip():stop('IPA ZIP CRC failed')
        base='Payload/Blender3GS.app/'
        info=plistlib.loads(z.read(base+'Info.plist'))
        if str(info.get('CFBundleVersion'))!='37' or info.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python' or info.get('UIApplicationExitsOnSuspend') is not False:stop('IPA identity mismatch')
        for rel,pat in ((UI,ui),(OPS,ops)):
            if z.read(base+'2.64/'+rel)!=pat.encode():stop('IPA staged package mismatch: '+rel)
    print('SUCCESS: UI37 DEVICE TEST CANDIDATE:',ipa,flush=True)
    print('CHECK: full 227 panels after UI37 STAGE batch completion; icon buffer may cost menu FPS.',flush=True)
    print('No background retention guarantee. Save work before testing new build.',flush=True)
if __name__=='__main__':main()
