#!/usr/bin/env python3
"""Blender3GS UI39: controlled 3D Core/Full A-B experiment, source-built UI38 IPA.

No binary patching or change of bundle identifier. Core disables UI modules by
omitting *automatic import/registration*, not by deleting code or data files.
Full preserves the UI38 roster. Both avoid cold-start directory enumeration when
there are no enabled add-ons and only the three known bundled startup packages.
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

TAG='BLENDER3GS_UI39_DIRECT_STARTUP_CORE_20260925'
BASE='Blender3GS-python-ui-v38-fast-first-frame.ipa'
PREFIX='Payload/Blender3GS.app/'
UI='2.64/scripts/startup/bl_ui/__init__.py'
OPS='2.64/scripts/startup/bl_operators/__init__.py'
UTILS='2.64/scripts/modules/bpy/utils.py'
INITIAL_UI=('properties_animviz','properties_data_modifier','properties_render',
            'properties_object','properties_material','space_info','space_view3d','space_outliner')
INITIAL_OPS=('view3d','object','wm')
CORE_INITIAL_UI=('properties_data_modifier','properties_object','space_info','space_view3d','space_outliner')
CORE_INITIAL_OPS=('view3d','wm')
CORE_UI=(
 'properties_animviz','properties_data_camera','properties_data_empty','properties_data_lamp',
 'properties_data_mesh','properties_data_modifier','properties_material',
 'properties_object_constraint','properties_object','properties_render',
 'properties_scene','properties_texture','properties_world',
 'space_info','space_view3d','space_view3d_toolbar','space_outliner','space_filebrowser',
)
CORE_OPS=('anim','mesh','object','presets','view3d','wm')
# Full A/B baseline preserves all UI38 UI modules, operators and registration.
CONFIG={'core':{'version':'39','output':'Blender3GS-python-ui-v39-3d-core.ipa'},
        'full':{'version':'40','output':'Blender3GS-python-ui-v39-full-direct-startup.ipa'}}

def stop(s):raise SystemExit('STOP: '+s)
def sha(b):return hashlib.sha256(b).hexdigest()

def ast_tuple(src,name):
 for node in ast.parse(src).body:
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
   return tuple(ast.literal_eval(node.value))
 stop('missing variable '+name)

def patch_roster(src,wanted,initial,label,expected_size,old_initial):
 if 'BLENDER3GS_UI38_FAST_FIRST_REAL_FRAME_20260925' not in src:
  stop(label+': expected UI38 staged loader marker')
 if TAG in src:stop(label+': already patched')
 original=ast_tuple(src,'_modules')
 if len(original)!=expected_size:stop(label+': unexpected stock module count '+str(len(original)))
 if len(set(original))!=len(original) or set(wanted)-set(original):stop(label+': unsupported module names')
 if set(initial)-set(wanted):stop(label+': missing initial modules in selected roster')
 if ast_tuple(src,'_ui37_initial') != old_initial:stop(label+': UI38 initial roster changed')
 # Keep stock order to preserve class registration and dependency ordering.
 selected=tuple(x for x in original if x in wanted)
 pattern=r'(?m)^_modules = \(\n(?:(?:\s*"[^"\n]+",\n)+)\)'
 m=re.search(pattern,src)
 if m is None or len(re.findall(pattern,src))!=1:stop(label+': unexpected tuple syntax')
 value='_modules = (\n'+''.join('    '+repr(n)+',\n' for n in selected)+')'
 out=src[:m.start()]+value+src[m.end():]
 # Fewer eager modules are the first-frame speed experiment; the rest are
 # imported from the retained core roster on the existing WM-stage path.
 before='_ui37_initial = '+repr(tuple(old_initial))
 if out.count(before)!=1:stop(label+': initial assignment shape differs')
 out=out.replace(before,'_ui37_initial = '+repr(tuple(initial)),1)
 # UI38's helper computes _ui37_deferred directly from _modules at import.
 if '_ui37_deferred = [name for name in _modules if name not in _ui37_initial]' not in out:
  stop(label+': deferred list not derived from roster')
 if 'def _ui37_step():' not in out:stop(label+': missing deferred function')
 # UI38 keeps retrying and raising from batch 9 through batch 30 even
 # after the import queue is empty. A Core build must stop work when done,
 # and report failures once rather than turning every subsequent frame red.
 marker='def _ui37_step():\n'
 if out.count(marker)!=1:stop(label+': UI38 helper mismatch')
 head=out[:out.index(marker)]
 if not out.rstrip().endswith('return len(_ui37_deferred)'):
  stop(label+': UI38 helper is not final source block')
 helper='''# %s: bounded worker on Blender main thread; never silently drop errors.
_ui39_finished = False
_ui39_grace = 0

def _ui37_step():
    global _ui39_finished, _ui39_grace
    if _ui39_finished:
        return 0
    import bpy
    for _ui39_index in range(2):
        if not _ui37_deferred:
            break
        name = _ui37_deferred.pop(0)
        try:
            package = __import__(name=__name__, fromlist=(name,))
            _modules_loaded[name] = getattr(package, name)
        except Exception as exc:
            _ui37_failures.append((name, repr(exc)))
            import traceback
            traceback.print_exc()
    pending = tuple(bpy.utils._bpy_module_classes(__name__, is_registered=False))
    for cls in pending:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            # Dependency may be supplied by the next package.
            pass
    if _ui37_deferred:
        return len(_ui37_deferred)
    _ui39_grace += 1
    if _ui39_grace < 3:
        return 0
    _ui39_finished = True
    pending = tuple(bpy.utils._bpy_module_classes(__name__, is_registered=False))
    if _ui37_failures or pending:
        raise RuntimeError('UI39 core incomplete %%s: imports=%%r pending=%%r' %%
                           (__name__, _ui37_failures, [c.__name__ for c in pending]))
    return 0
'''%(TAG,)
 out=head+helper
 compile(out,label,'exec')
 print('PROFILE',label,'selected',len(selected),'of',len(original),'initial',len(initial),'deferred',len(selected)-len(initial))
 return out

def patch_utils(src):
 if TAG in src:stop('utils already patched')
 anchor='''    for base_path in script_paths():
        for path_subdir in _script_module_dirs:
            path = _os.path.join(base_path, path_subdir)
            if _os.path.isdir(path):
                _sys_path_ensure(path)

                # only add this to sys.modules, don't run
                if path_subdir == "modules":
                    continue

                for mod in modules_from_path(path, loaded_modules):
                    test_register(mod)

    # deal with addons separately
    _addon_utils.reset_all(reload_scripts)
'''
 if src.count(anchor)!=1:stop('bpy.utils.load_scripts differs from known Blender 2.64 source')
 replacement='''    # %s: cold-start fast path for the *exact* bundled startup tree.
    # Do not enumerate all possible script paths or scan unused add-on folders.
    # Never take this path on reload/refresh or with any enabled add-ons.
    # Package guard ensures only keyingsets_builtins, bl_operators and bl_ui
    # are present as top-level default startup scripts in this particular IPA.
    if not reload_scripts and not refresh_scripts and not prefs.addons:
        _ui39_scripts = _os.path.normpath(_os.path.join(
            _os.path.dirname(__file__), _os.path.pardir, _os.path.pardir))
        _sys_path_ensure(_os.path.join(_ui39_scripts, "modules"))
        _sys_path_ensure(_os.path.join(_ui39_scripts, "startup"))
        for _ui39_name in ("bl_operators", "bl_ui", "keyingsets_builtins"):
            test_register(_test_import(_ui39_name, loaded_modules))
    else:
        for base_path in script_paths():
            for path_subdir in _script_module_dirs:
                path = _os.path.join(base_path, path_subdir)
                if _os.path.isdir(path):
                    _sys_path_ensure(path)
                    if path_subdir == "modules":
                        continue
                    for mod in modules_from_path(path, loaded_modules):
                        test_register(mod)

    # An empty add-on preference list has nothing to enable at cold start.
    # Retain stock reset behavior for every other path.
    if reload_scripts or refresh_scripts or prefs.addons:
        _addon_utils.reset_all(reload_scripts)
'''%TAG
 out=src.replace(anchor,replacement,1)
 compile(out,UTILS,'exec')
 return out

def checked_source(z):
 if z.testzip():stop('input IPA CRC failure')
 names=z.namelist();ns=set(names)
 if len(ns)!=len(names):stop('duplicate filenames in IPA')
 if any(n.startswith('/') or '..' in Path(n).parts for n in names):stop('unsafe path in input IPA')
 required={PREFIX+'Blender3GS',PREFIX+'Info.plist',PREFIX+UI,PREFIX+OPS,PREFIX+UTILS}
 if not required.issubset(ns):stop('missing IPA assets')
 meta=plistlib.loads(z.read(PREFIX+'Info.plist'))
 if (str(meta.get('CFBundleVersion'))!='38' or meta.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python' or
     meta.get('UIApplicationExitsOnSuspend') is not False):stop('expected UI38 identity/version/background flag')
 startup=PREFIX+'2.64/scripts/startup/'
 top=set()
 for n in names:
  if n.startswith(startup):
   rel=n[len(startup):]
   if not rel:continue
   first=rel.split('/')[0]
   if first.startswith('.') or first=='__pycache__':continue
   if first.endswith('.py') or '/' in rel:top.add(first)
 if top != {'bl_ui','bl_operators','keyingsets_builtins.py'}:
  stop('startup tree differs: '+repr(sorted(top)))
 ui=z.read(PREFIX+UI).decode('utf8');ops=z.read(PREFIX+OPS).decode('utf8');utils=z.read(PREFIX+UTILS).decode('utf8')
 # Do not optimize an unknown/locally edited bpy.utils implementation.
 if '_addon_utils.reset_all(reload_scripts)' not in utils:stop('unknown bpy.utils')
 return meta,ui,ops,utils

def for_preset(preset,ui,ops,utils):
 if preset=='core':
  return {UI:patch_roster(ui,CORE_UI,CORE_INITIAL_UI,'bl_ui',47,INITIAL_UI),
          OPS:patch_roster(ops,CORE_OPS,CORE_INITIAL_OPS,'bl_operators',20,INITIAL_OPS),
          UTILS:patch_utils(utils)}
 # Full profile is a clean control to measure the benefit of the direct-load
 # shortcut alone. It does not remove any UI modules or operators.
 if len(ast_tuple(ui,'_modules'))!=47 or len(ast_tuple(ops,'_modules'))!=20:
  stop('unknown full source roster')
 return {UTILS:patch_utils(utils)}

def run(*argv,cwd=None):
 print('COMMAND:', ' '.join(map(str,argv)),flush=True)
 subprocess.run([str(x) for x in argv],cwd=cwd,check=True)

def package(root,preset,repl,base_hash):
 dest=root/CONFIG[preset]['output']
 if dest.exists():stop('output already exists (never overwrite): '+str(dest))
 for name in ('unzip','zip','ldid'):
  if not shutil.which(name):stop('missing on Mac: '+name)
 with tempfile.TemporaryDirectory(prefix='blender3gs-ui39-'+preset+'-') as d:
  stage=Path(d);run('unzip','-q',root/BASE,'-d',stage)
  app=stage/'Payload'/'Blender3GS.app'
  for rel,content in repl.items():
   p=app/rel
   if not p.is_file():stop('extracted package missing '+rel)
   p.write_text(content,encoding='utf8')
   for stale in [p.with_suffix('.pyc'),*list((p.parent/'__pycache__').glob(p.stem+'.*.pyc'))]:
    if stale.is_file():stale.unlink()
  with (app/'Info.plist').open('rb') as f:meta=plistlib.load(f)
  meta['CFBundleVersion']=CONFIG[preset]['version'];meta['CFBundleShortVersionString']='0.39.'+('0' if preset=='core' else '1')
  meta['CFBundleDisplayName']='Blender Py '+('Core' if preset=='core' else 'Full')
  with (app/'Info.plist').open('wb') as f:plistlib.dump(meta,f,fmt=plistlib.FMT_XML)
  shutil.rmtree(app/'_CodeSignature',ignore_errors=True)
  (app/'CodeResources').unlink(missing_ok=True)
  run('ldid','-S',app/'Blender3GS')
  partial=dest.with_suffix('.partial.ipa')
  if partial.exists():stop('stale partial output '+str(partial))
  try:
   run('zip','-qry',partial,'Payload',cwd=stage)
   with zipfile.ZipFile(partial) as z:
    if z.testzip():stop('generated IPA CRC error')
    info=plistlib.loads(z.read(PREFIX+'Info.plist'))
    if info.get('CFBundleVersion')!=meta['CFBundleVersion'] or info.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python':stop('generated Info.plist mismatch')
    for rel,src in repl.items():
     if z.read(PREFIX+rel)!=src.encode('utf8'):stop('packaged source mismatch '+rel)
    for rel in (UI,OPS,UTILS):
     if rel not in repl and sha(z.read(PREFIX+rel))!=sha((app/rel).read_bytes()):stop('unexpected source change '+rel)
    print('PASS: output CRC, expected version, checked Python source, same bundle identifier')
   os.replace(partial,dest)
  finally:
   if partial.exists():partial.unlink()
 print('SUCCESS:',dest,'source_ui38_sha256='+base_hash)
 return dest

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--root',type=Path,default=Path.home()/'Downloads')
 ap.add_argument('--preset',choices=CONFIG,default='core')
 ap.add_argument('--check-only',action='store_true')
 a=ap.parse_args();root=a.root.expanduser().resolve();base=root/BASE
 if not base.is_file():stop('missing UI38 base IPA: '+str(base))
 with zipfile.ZipFile(base) as z:
  _,ui,ops,utils=checked_source(z)
  repl=for_preset(a.preset,ui,ops,utils)
  binary=sha(z.read(PREFIX+'Blender3GS'))
  print('PASS: UI38 source',sha(base.read_bytes()),'native_executable_sha256',binary,'preset='+a.preset)
  print('PASS: only',len(repl),'text source file(s) change; no native Blender changes')
 if a.check_only:
  print('SUCCESS: CHECK ONLY; source file and previous IPAs untouched')
  return
 package(root,a.preset,repl,sha(base.read_bytes()))

if __name__=='__main__':main()
