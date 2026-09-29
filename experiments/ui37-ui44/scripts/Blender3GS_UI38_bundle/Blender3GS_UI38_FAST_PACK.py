#!/usr/bin/env python3
"""Blender3GS UI38: aggressive first-real-frame variant of a built UI37 IPA.

Keep native executable, assets, handlers, and all original Python modules; change
only the *startup order* of the two UI37 package loaders. This intentionally
trades temporarily incomplete Python UI for earlier real 3D viewport. Finish
remaining packages incrementally on the Blender WM thread.
"""
import argparse
import ast
import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

BASE='Blender3GS-python-ui-v37-staged-full-ui-buffer-icons.ipa'
OUT='Blender3GS-python-ui-v38-fast-first-frame.ipa'
TAG='BLENDER3GS_UI38_FAST_FIRST_REAL_FRAME_20260925'
PREFIX='Payload/Blender3GS.app/'
UI='2.64/scripts/startup/bl_ui/__init__.py'
OPS='2.64/scripts/startup/bl_operators/__init__.py'
# Essential native header/outliner plus the most-used Properties categories.
# The other ~40 UI modules are still imported and registered incrementally.
INITIAL_UI=('properties_animviz','properties_data_modifier','properties_render',
            'properties_object','properties_material','space_info',
            'space_view3d','space_outliner')
INITIAL_OPS=('view3d','object','wm')

def stop(msg): raise SystemExit('STOP: '+msg)
def digest(data): return hashlib.sha256(data).hexdigest()

def tuple_from_ast(src, var):
    tree=ast.parse(src)
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id==var for x in node.targets):
            return tuple(ast.literal_eval(node.value))
    stop('missing tuple: '+var)

def patch_loader(src, initial, label):
    if TAG in src: stop('already UI38: '+label)
    if 'BLENDER3GS_UI37_STAGE_REAL_UI_ICON_BUFFER_20260924' not in src:
        stop('not UI37 staged loader: '+label)
    m=re.search(r'^_ui37_initial = (.+)$',src,re.M)
    if m is None or len(re.findall(r'^_ui37_initial = ',src,re.M))!=1:
        stop('UI37 initial assignment not uniquely found: '+label)
    former=tuple(ast.literal_eval(m.group(1)))
    original_all=tuple_from_ast(src,'_modules')
    if not set(initial).issubset(original_all):stop('missing essential modules: '+label)
    if not set(former).issubset(original_all):stop('UI37 module list changed: '+label)
    # Ensure known-old loader is the exact shape we have actually examined.
    if len(original_all)<15 or 'def _ui37_step():\n' not in src:
        stop('unknown UI37 loader: '+label)
    if src.count('def _ui37_step():\n')!=1 or '    return len(_ui37_deferred) + 1\n' not in src:
        stop('unknown UI37 staged function: '+label)
    src=src[:m.start(1)]+repr(tuple(initial))+src[m.end(1):]
    start=src.index('def _ui37_step():\n')
    # Previous UI37 helper is appended after the stock register/unregister
    # routines. It is deliberately the last source block.
    old_func=src[start:]
    if not old_func.rstrip().endswith('return len(_ui37_deferred) + 1'):
        stop('UI37 function is no longer the final source block: '+label)
    new_func='''def _ui37_step():
    # %s. Keep the UI37 C caller (30 steps), import at most two packages
    # per step. All changes stay on Blender's own WM/Python thread.
    import bpy
    for _ui38_index in range(2):
        if not _ui37_deferred:
            break
        name = _ui37_deferred.pop(0)
        try:
            package = __import__(name=__name__, fromlist=(name,))
            mod = getattr(package, name)
            _modules_loaded[name] = mod
        except Exception as exc:
            _ui37_failures.append((name, repr(exc)))
            import traceback
            traceback.print_exc()
    # Retry previously unregistered classes after dependencies have appeared.
    # Unlike UI37's per-step register_module, an empty class set is normal.
    for _ui38_cls in tuple(bpy.utils._bpy_module_classes(__name__, is_registered=False)):
        try:
            bpy.utils.register_class(_ui38_cls)
        except Exception:
            # Some classes require later modules; retry on the following step.
            pass
    if not _ui37_deferred:
        _ui38_pending = tuple(bpy.utils._bpy_module_classes(__name__, is_registered=False))
        if _ui37_failures or _ui38_pending:
            raise RuntimeError("UI38 incomplete %%s: imports=%%r pending=%%r" %%
                               (__name__, _ui37_failures, [c.__name__ for c in _ui38_pending]))
    return len(_ui37_deferred)
''' % TAG
    new=src[:start]+new_func
    if new.count(TAG)!=1:stop('tag missing: '+label)
    compile(new,label,'exec')
    print('PASS:',label,'initial',len(initial),'from',len(former),'deferred',len(original_all)-len(initial))
    return new

def validate_zip(z):
    if z.testzip():stop('source IPA fails CRC')
    names=set(z.namelist())
    required={PREFIX+'Info.plist',PREFIX+'Blender3GS',PREFIX+UI,PREFIX+OPS}
    if not required.issubset(names):stop('source IPA missing expected files')
    if any(n.startswith('/') or '..' in Path(n).parts for n in names):stop('unsafe ZIP path')
    info=plistlib.loads(z.read(PREFIX+'Info.plist'))
    if (str(info.get('CFBundleVersion'))!='37' or
            info.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python' or
            info.get('UIApplicationExitsOnSuspend') is not False):
        stop('not expected UI37 IPA (identity/version/suspend flag)')
    return info

def run(*argv,cwd=None):
    print('COMMAND:', ' '.join(map(str,argv)),flush=True)
    subprocess.run([str(x) for x in argv],cwd=cwd,check=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path.home()/'Downloads')
    ap.add_argument('--check-only',action='store_true')
    ap.add_argument('--allow-overwrite',action='store_true',help='only for intentional re-test of generated UI38 IPA')
    args=ap.parse_args()
    root=args.root.expanduser().resolve(); source=root/BASE; dest=root/OUT
    if not source.is_file():stop('missing UI37 IPA: '+str(source))
    with zipfile.ZipFile(source) as z:
        info=validate_zip(z)
        replacements={UI:patch_loader(z.read(PREFIX+UI).decode('utf-8'),INITIAL_UI,UI),
                      OPS:patch_loader(z.read(PREFIX+OPS).decode('utf-8'),INITIAL_OPS,OPS)}
        print('PASS: source IPA bytes',source.stat().st_size,'sha256',digest(source.read_bytes()))
    if args.check_only:
        print('SUCCESS: CHECK ONLY. Nothing changed. UI37 original remains untouched.')
        return
    if dest.exists() and not args.allow_overwrite:stop('output exists (no overwrite): '+str(dest))
    for cmd in ('unzip','zip','ldid','file'):
        if shutil.which(cmd) is None:stop('missing on Mac: '+cmd)
    with tempfile.TemporaryDirectory(prefix='blender3gs-ui38-') as d:
        stage=Path(d)
        run('unzip','-q',source,'-d',stage)
        app=stage/'Payload'/'Blender3GS.app'
        for rel,src in replacements.items():
            p=app/rel
            if not p.is_file():stop('missing extracted: '+str(p))
            p.write_text(src,encoding='utf-8')
        # The bundle currently has no writable .pyc cache. Remove stale bytecode
        # only for the two edited modules, leaving every other resource intact.
        for rel in replacements:
            p=app/rel
            pyc=p.with_suffix('.pyc')
            if pyc.is_file():pyc.unlink()
            cache=p.parent/'__pycache__'
            if cache.is_dir():
                for old in cache.glob(p.stem+'.*.pyc'):old.unlink()
        plist=app/'Info.plist'
        with plist.open('rb') as f:newinfo=plistlib.load(f)
        newinfo['CFBundleVersion']='38'
        newinfo['CFBundleShortVersionString']='0.38.0'
        with plist.open('wb') as f:plistlib.dump(newinfo,f,fmt=plistlib.FMT_XML)
        shutil.rmtree(app/'_CodeSignature',ignore_errors=True)
        (app/'CodeResources').unlink(missing_ok=True)
        run('ldid','-S',app/'Blender3GS')
        tmpdest=dest.with_suffix('.partial.ipa')
        if tmpdest.exists():stop('partial package exists: '+str(tmpdest))
        try:
            run('zip','-qry',tmpdest,'Payload',cwd=stage)
            with zipfile.ZipFile(tmpdest) as z:
                check=plistlib.loads(z.read(PREFIX+'Info.plist'))
                if z.testzip() or str(check['CFBundleVersion'])!='38':stop('output ZIP invalid')
                for rel,data in replacements.items():
                    if z.read(PREFIX+rel)!=data.encode('utf-8'):stop('packaged loader mismatch: '+rel)
                print('PASS: unchanged native architecture and asset set; updated exactly two Python loader files')
            os.replace(tmpdest,dest)
        finally:
            if tmpdest.exists():tmpdest.unlink()
    print('SUCCESS: UI38 IPA:',dest)
    print('NOTE: faster real first frame is experimental; it may briefly show limited panels while the rest register.')
    print('NOTE: background retention requires a separate compatible iOS 6 tweak or a lifecycle refactor.')
if __name__=='__main__':main()
