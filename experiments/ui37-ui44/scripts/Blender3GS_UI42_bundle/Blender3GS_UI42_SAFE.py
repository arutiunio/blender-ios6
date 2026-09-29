#!/usr/bin/env python3
"""UI42 A/B visual regression isolation: preserve UI41 fast path but never swap View3D drawtype.

This builds over the exact UI41 IPA already on the user's Mac; source check is non-mutating.
"""
import argparse
import hashlib
import os
import plistlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

TAG='BLENDER3GS_UI42_SAFE_NATIVE_SHADE_20260925'
REL='source/blender/windowmanager/intern/wm_draw.c'
BASE='Blender3GS-python-ui-v41-mega-first-frame.ipa'
OUT='Blender3GS-python-ui-v42-safe-viewport.ipa'
PFX='Payload/Blender3GS.app/'

def stop(msg): raise SystemExit('STOP: '+msg)
def sha(b): return hashlib.sha256(b).hexdigest()
def once(s,old,new,name):
    if s.count(old)!=1: stop('%s: expected 1 anchor, got %d' % (name,s.count(old)))
    return s.replace(old,new,1)

def patch_draw(s):
    if TAG in s: stop('source already UI42; use --resume')
    for anchor in ('BLENDER3GS_UI41_MEGA_BOOT_20260925',
                   'BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925',
                   'ui41_v3d->drawtype = OB_BOUNDBOX;',
                   'ui41_v3d->drawtype = ui41_saved_drawtype;',
                   'Blender3GS UI41 MEGA: bbox_preview_begin',
                   'Blender3GS UI41 MEGA: bbox_preview_end'):
        if anchor not in s: stop('not the exact working UI41 draw source: '+anchor)
    # Preserve the existing drawtype for the first frame. Do not change
    # Python stage order, draw compositor, original shading, or other editors.
    s=once(s,'ui41_v3d->drawtype = OB_BOUNDBOX;',
        '/* %s: leave original shading intact; bbox GL path disabled. */' % TAG,
        'remove bbox state mutation')
    s=once(s,'Blender3GS UI41 MEGA: bbox_preview_begin',
        'Blender3GS UI42 SAFE: viewport_shading_unchanged', 'correct begin diagnostic')
    s=once(s,'Blender3GS UI41 MEGA: bbox_preview_end',
        'Blender3GS UI42 SAFE: viewport_shading_still_unchanged', 'correct end diagnostic')
    # No-op restoration remains deliberately: same C control flow as UI41.
    return s

def verify_ipa(path,version):
    if not path.is_file(): stop('missing IPA '+str(path))
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        if bad: stop('IPA bad CRC '+bad)
        names=z.namelist()
        if len(set(names))!=len(names) or any(n.startswith('/') or '..' in Path(n).parts for n in names): stop('unsafe/duplicate IPA path')
        for name in ('Info.plist','Blender3GS','2.64/scripts/startup/bl_ui/__init__.py'):
            if PFX+name not in names: stop('missing IPA file '+name)
        meta=plistlib.loads(z.read(PFX+'Info.plist'))
        if str(meta.get('CFBundleVersion'))!=str(version) or meta.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python' or meta.get('UIApplicationExitsOnSuspend') is not False:
            stop('expected UI%d IPA with original bundle ID/suspend setting, got %r' % (version,{k:meta.get(k) for k in ('CFBundleVersion','CFBundleIdentifier','UIApplicationExitsOnSuspend')}))
        return sha(z.read(PFX+'Blender3GS')),set(names)

def run(step,args,log=None,cwd=None):
    print('=== %s ===' % step, flush=True)
    print('COMMAND:', ' '.join(map(str,args)),flush=True)
    if log:
        with log.open('w') as f:
            p=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT,cwd=cwd)
        if p.returncode:stop('%s exit=%d; log: %s\n%s' % (step,p.returncode,log,log.read_text(errors='replace')[-10000:]))
    else: subprocess.run(list(map(str,args)),check=True,cwd=cwd)

def package(exe,base,out):
    for dep in ('unzip','zip','ldid'):
        if not shutil.which(dep):stop('missing '+dep)
    with tempfile.TemporaryDirectory(prefix='blender3gs-ui42-') as temp:
        work=Path(temp)
        run('unpack verified UI41', ['unzip','-q',base,'-d',work])
        app=work/'Payload'/'Blender3GS.app'
        binfile=app/'Blender3GS';shutil.copy2(exe,binfile)
        pl=app/'Info.plist';info=plistlib.loads(pl.read_bytes())
        info['CFBundleVersion']='43';info['CFBundleShortVersionString']='0.42.0'
        info['CFBundleDisplayName']='Blender Py Safe'
        info['UIApplicationExitsOnSuspend']=False
        pl.write_bytes(plistlib.dumps(info,fmt=plistlib.FMT_XML))
        shutil.rmtree(app/'_CodeSignature',ignore_errors=True)
        (app/'CodeResources').unlink(missing_ok=True)
        run('sign UI42', ['ldid','-S',binfile])
        part=out.with_name(out.stem+'.partial.ipa')
        if part.exists(): stop('stale partial IPA exists: '+str(part))
        try:
            run('package UI42', ['zip','-qry',part,'Payload'],cwd=work)
            bsha,roster=verify_ipa(part,43)
            oldsha,oldroster=verify_ipa(base,42)
            if bsha!=sha(binfile.read_bytes()) or bsha==oldsha:stop('packaged binary identity mismatch or unchanged')
            if roster!=oldroster:stop('IPA roster changed unexpectedly')
            with zipfile.ZipFile(base) as old,zipfile.ZipFile(part) as new:
                for n in roster:
                    if n in (PFX+'Blender3GS',PFX+'Info.plist'):continue
                    if old.read(n)!=new.read(n):stop('other asset changed: '+n)
            os.replace(part,out)
        finally: part.unlink(missing_ok=True)
    print('SUCCESS: UI42 SAFE IPA: '+str(out),flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path.home()/'Downloads')
    ap.add_argument('--check-only',action='store_true')
    ap.add_argument('--resume',action='store_true')
    a=ap.parse_args();root=a.root.expanduser().resolve()
    src=root/'blender-ios6-target'/REL
    backup=src.with_name(src.name+'.before-'+TAG)
    out=root/OUT;base=root/BASE
    oldsha,_=verify_ipa(base,42)
    if out.exists():stop('output IPA already exists; use --install-only')
    if not src.is_file():stop('missing source '+str(src))
    if a.resume and not backup.exists():stop('no UI42 backup: previous check stopped before patch; run normal command')
    if not a.resume and backup.exists():stop('UI42 backup already exists; use --resume only if patched file matches')
    transformed=patch_draw((backup if a.resume else src).read_text())
    if a.resume and src.read_text()!=transformed: stop('patched source differs from expected; refusing resume')
    print('PASS: exact UI41 drawing anchors; baseline binary sha256='+oldsha,flush=True)
    print('PLAN: preserve UI41 WM/Python staging and first C frame, never switch to Bounding Box',flush=True)
    if a.check_only:
        print('CHECK ONLY: no files modified',flush=True);return
    build=root/'blender-ios6-build-python';work=root/'blender-ios6-python';exe=root/'Blender3GS-python-armv7';link=root/'blender-link-ios-python-v3.py'
    for p in (build/'build.ninja',exe,link):
        if not p.is_file():stop('missing prerequisite '+str(p))
    if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):stop('DEVELOPER_DIR/IOS_SDKROOT not set')
    work.mkdir(exist_ok=True)
    if not a.resume:
        shutil.copy2(src,backup)
        src.write_text(transformed)
        print('BACKUP + PATCH: '+str(src),flush=True)
    run('compile ARMv7 window manager',['ninja','-C',build,'-j4','bf_windowmanager'],work/'ui-v42-build.log')
    run('relink ARMv7',['python3',link],work/'ui-v42-link.log')
    run('verify armv7',['xcrun','lipo','-info',exe],work/'ui-v42-arch.log')
    if 'armv7' not in (work/'ui-v42-arch.log').read_text().lower():stop('not armv7')
    package(exe,base,out)

if __name__=='__main__':main()
