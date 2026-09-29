#!/usr/bin/env python3
"""UI44 FOCUS: scoped GL region draws, contained stock icon quads, safe 3D
Camera/Lamp world-space crosses. Exact tested UI43 native source & IPA only.

Never runs the iOS compiler on the host. Provides strict preflight, atomic
source backups, native rebuild on Mac, signed IPA verification and USB install
via paired shell wrapper. GPL patch to Blender 2.64 source (not a prebuilt app).
"""
import argparse
import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

TAG='BLENDER3GS_UI44_SCOPED_VISUAL_FOCUS_20260925'
DRAW='source/blender/windowmanager/intern/wm_draw.c'
ICONS='source/blender/editors/interface/interface_icons.c'
OBJECT='source/blender/editors/space_view3d/drawobject.c'
BASE='Blender3GS-python-ui-v43-visual-diagnostic.ipa'
OUT='Blender3GS-python-ui-v44-focus.ipa'
PFX='Payload/Blender3GS.app/'

def fail(s):raise SystemExit('STOP: '+s)
def sha(b):return hashlib.sha256(b).hexdigest()
def once(s,old,new,msg):
    n=s.count(old)
    if n!=1:fail('%s: expected 1 exact anchor, got %d'%(msg,n))
    return s.replace(old,new,1)

def patch_draw(s):
    if TAG in s:fail('wm_draw.c already UI44')
    for x in ('BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925',
              'BLENDER3GS_UI41_MEGA_BOOT_20260925',
              'BLENDER3GS_UI43_VISUAL_DIAGNOSTIC_20260925',
              'static void wm_method_draw_full(bContext *C, wmWindow *win)',
              'ED_region_do_draw(C, ar);'):
        if x not in s:fail('wm_draw.c missing UI43 anchor '+x)
    count=s.count('ED_region_do_draw(C, ar);')
    if not (5<=count<=16):fail('unexpected region call count: %d'%count)
    # This protects scissor / depth / culling at region boundaries. Unlike an
    # unscoped "hard reset", it restores state after Blender finishes drawing.
    helper='''/* %s: isolate each iOS region's GLES state; preserve Blender's
 * window-retained redraw and UI40/UI41 early native Viewport. */
static void ui44_draw_region_scoped(bContext *C, ARegion *ar)
{
#ifdef WITH_IOS
    GLint old_scissor[4];
    GLboolean scissor_was_on = glIsEnabled(GL_SCISSOR_TEST);
    GLboolean depth_was_on = glIsEnabled(GL_DEPTH_TEST);
    GLboolean cull_was_on = glIsEnabled(GL_CULL_FACE);
    ScrArea *sa = CTX_wm_area(C);
    const int width = ar->winrct.xmax - ar->winrct.xmin + 1;
    const int height = ar->winrct.ymax - ar->winrct.ymin + 1;
    glGetIntegerv(GL_SCISSOR_BOX, old_scissor);
    if (sa && sa->spacetype != SPACE_VIEW3D) {
        /* UI is 2D. Do not let a previous mesh pass reject UI fragments. */
        glDisable(GL_DEPTH_TEST);
        glDisable(GL_CULL_FACE);
    }
    if (width > 0 && height > 0) {
        glEnable(GL_SCISSOR_TEST);
        glScissor(ar->winrct.xmin, ar->winrct.ymin, width, height);
    }
    ED_region_do_draw(C, ar);
    glScissor(old_scissor[0], old_scissor[1], old_scissor[2], old_scissor[3]);
    if (scissor_was_on) glEnable(GL_SCISSOR_TEST);
    else glDisable(GL_SCISSOR_TEST);
    if (depth_was_on) glEnable(GL_DEPTH_TEST);
    else glDisable(GL_DEPTH_TEST);
    if (cull_was_on) glEnable(GL_CULL_FACE);
    else glDisable(GL_CULL_FACE);
#else
    ED_region_do_draw(C, ar);
#endif
}

'''%TAG
    # Replacing the calls before insertion prevents recursion, including the
    # unmodified path for non-iOS platforms.
    s=s.replace('ED_region_do_draw(C, ar);','ui44_draw_region_scoped(C, ar);')
    s=once(s,'static void wm_method_draw_full(bContext *C, wmWindow *win)',
           helper+'static void wm_method_draw_full(bContext *C, wmWindow *win)',
           'insert bounded region guard')
    # Diagnostic marker only, no logging every frame.
    s=once(s, '    GLint old_scissor[4];',
           '    GLint old_scissor[4];\n    static int ui44_region_logged = 0;\n    if (!ui44_region_logged++) syslog(LOG_WARNING, "Blender3GS UI44 FOCUS: scoped_region_GL=1");',
           'guard init')
    return s

def patch_icons(s):
    if TAG in s:fail('interface_icons.c already UI44')
    for x in ('BLENDER3GS_UI43_VISUAL_DIAGNOSTIC_20260925',
              'tiny_icon_texture_ok', 'if (iimg->ui43_tex) {',
              'IconTexture old_texture = icongltex;',
              'icon_draw_texture(x, y, (float)w, (float)h, 0, 0,'):
        if x not in s:fail('interface_icons.c missing UI43 anchor '+x)
    # The white 40x32 rectangle and long 1px lines cross editor boundaries.
    # Confine every stock bitmap quad to its own icon viewport intersection.
    # Texture creation/caching & GL4ES renderer stay unchanged. Restore the
    # previously active scissor rectangle on ALL paths.
    old='''        if (iimg->ui43_tex) {
            IconTexture old_texture = icongltex;
            icongltex.id = iimg->ui43_tex;
            icongltex.w = iimg->w; icongltex.h = iimg->h;
            icongltex.invw = 1.0f / (float)iimg->w;
            icongltex.invh = 1.0f / (float)iimg->h;
            icon_draw_texture(x, y, (float)w, (float)h, 0, 0,
                              iimg->w, iimg->h, alpha, rgb);
            icongltex = old_texture;
        }'''
    new='''        if (iimg->ui43_tex) {
            /* %s: GL4ES icon quad must not spill into unrelated
             * editor regions. Keep existing tiny texture cache. */
            const GLboolean had_scissor = glIsEnabled(GL_SCISSOR_TEST);
            GLint prior_scissor[4], vp[4];
            int sx, sy, ex, ey;
            IconTexture old_texture = icongltex;
            glGetIntegerv(GL_SCISSOR_BOX, prior_scissor);
            glGetIntegerv(GL_VIEWPORT, vp);
            /* Drawing coordinates are region-local under the Blender 2D
             * subwindow. Allow one pixel on each edge for glyph antialias. */
            sx = vp[0] + (int)x - 1;
            sy = vp[1] + (int)y - 1;
            ex = sx + w + 2;
            ey = sy + h + 2;
            if (had_scissor) {
                if (sx < prior_scissor[0]) sx = prior_scissor[0];
                if (sy < prior_scissor[1]) sy = prior_scissor[1];
                if (ex > prior_scissor[0] + prior_scissor[2]) ex = prior_scissor[0] + prior_scissor[2];
                if (ey > prior_scissor[1] + prior_scissor[3]) ey = prior_scissor[1] + prior_scissor[3];
            }
            /* Always intersect icon draw with current subwindow viewport. */
            if (sx < vp[0]) sx = vp[0];
            if (sy < vp[1]) sy = vp[1];
            if (ex > vp[0] + vp[2]) ex = vp[0] + vp[2];
            if (ey > vp[1] + vp[3]) ey = vp[1] + vp[3];
            if (ex > sx && ey > sy) {
                glEnable(GL_SCISSOR_TEST);
                glScissor(sx, sy, ex - sx, ey - sy);
                icongltex.id = iimg->ui43_tex;
                icongltex.w = iimg->w; icongltex.h = iimg->h;
                icongltex.invw = 1.0f / (float)iimg->w;
                icongltex.invh = 1.0f / (float)iimg->h;
                icon_draw_texture(x, y, (float)w, (float)h, 0, 0,
                                  iimg->w, iimg->h, alpha, rgb);
                icongltex = old_texture;
            }
            glScissor(prior_scissor[0], prior_scissor[1], prior_scissor[2], prior_scissor[3]);
            if (had_scissor) glEnable(GL_SCISSOR_TEST);
            else glDisable(GL_SCISSOR_TEST);
            {
                static int ui44_icons_reported = 0;
                if (!ui44_icons_reported++)
                    syslog(LOG_WARNING, "Blender3GS UI44 FOCUS: icon_scissor=1 viewport=%%d,%%d,%%d,%%d",
                           vp[0], vp[1], vp[2], vp[3]);
            }
        }'''%TAG
    return once(s,old,new,'scope existing tiny-icon render')

def patch_object(s):
    if TAG in s:fail('drawobject.c already UI44')
    exact='''        if (ui43_type == OB_CAMERA || ui43_type == OB_LAMP) {
            static int ui43_camera_logged = 0, ui43_lamp_logged = 0;'''
    if s.count(exact)!=1:fail('drawobject.c missing exact UI43 isolated Camera/Lamp guard')
    old='''            return;
        }
    }
#endif'''
    if s.count(old)!=1:fail('drawobject.c changed around UI43 return')
    # Use a tiny WORLD-SPACE cross centered at each object's transform, under
    # the already-configured view matrix. No filled triangles, no camera cone,
    # no glMultMatrix/glPushMatrix. Render only when object is visible in view.
    # Existing object data/render/picking unaffected.
    new='''            /* %s: replace old helper geometry with a minimal
             * world-space cross. No legacy GL wire camera/spot cone path. */
            {
                const float *p = base->object->obmat[3];
                const float r = (ui43_type == OB_CAMERA) ? 0.28f : 0.16f;
                const GLboolean old_depth = glIsEnabled(GL_DEPTH_TEST);
                glDisable(GL_DEPTH_TEST);
                if (ui43_type == OB_CAMERA)
                    gpuCurrentColor4f(0.45f, 0.75f, 1.0f, 1.0f);
                else
                    gpuCurrentColor4f(1.0f, 0.92f, 0.38f, 1.0f);
                gpuImmediateFormat_V3();
                gpuBegin(GL_LINES);
                gpuVertex3f(p[0]-r, p[1], p[2]); gpuVertex3f(p[0]+r, p[1], p[2]);
                gpuVertex3f(p[0], p[1]-r, p[2]); gpuVertex3f(p[0], p[1]+r, p[2]);
                gpuVertex3f(p[0], p[1], p[2]-r); gpuVertex3f(p[0], p[1], p[2]+r);
                gpuEnd();
                gpuImmediateUnformat();
                if (old_depth) glEnable(GL_DEPTH_TEST);
                else glDisable(GL_DEPTH_TEST);
                { static int ui44_markers_reported = 0;
                  if (!ui44_markers_reported++)
                      syslog(LOG_WARNING, "Blender3GS UI44 FOCUS: safe_camera_lamp_crosses=1"); }
            }
            return;
        }
    }
#endif'''%TAG
    return once(s,old,new,'replace only isolated helper return')

def verify(path,version):
    if not path.is_file():fail('missing baseline UI43 IPA: '+str(path))
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        if bad:fail('IPA CRC failed: '+bad)
        names=z.namelist()
        if len(names)!=len(set(names)) or any(n.startswith('/') or '..' in Path(n).parts for n in names):
            fail('IPA contains unsafe or duplicated members')
        for rel in ('Info.plist','Blender3GS','2.64/scripts/startup/bl_ui/__init__.py'):
            if PFX+rel not in names:fail('IPA missing '+rel)
        pl=plistlib.loads(z.read(PFX+'Info.plist'))
        if (str(pl.get('CFBundleVersion'))!=str(version) or
            pl.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python' or
            pl.get('UIApplicationExitsOnSuspend') is not False):
            fail('expected UI%s original app ID, exitsOnSuspend=false; got %r' %
                 (version,{k:pl.get(k) for k in ('CFBundleVersion','CFBundleIdentifier','UIApplicationExitsOnSuspend')}))
        return sha(z.read(PFX+'Blender3GS')),set(names)

def run(label,cmd,log=None,cwd=None):
    print('=== %s ==='%label,flush=True)
    print('COMMAND: '+' '.join(map(str,cmd)),flush=True)
    if log:
        with log.open('w') as f:rc=subprocess.run(list(map(str,cmd)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        if rc.returncode:fail('%s failed exit=%d; log=%s\n%s'%
                              (label,rc.returncode,log,log.read_text(errors='replace')[-14000:]))
    else:
        rc=subprocess.run(list(map(str,cmd)),cwd=cwd)
        if rc.returncode:fail('%s failed exit=%d'%(label,rc.returncode))

def package(exe,base,out):
    for tool in ('zip','unzip','ldid'):
        if not shutil.which(tool):fail('host tool missing: '+tool)
    base_sha,roster=verify(base,44)
    with tempfile.TemporaryDirectory(prefix='Blender3GS-ui44-') as d:
        td=Path(d);run('unpack immutable UI43 baseline',['unzip','-q',base,'-d',td])
        app=td/'Payload'/'Blender3GS.app'
        unsigned=sha(exe.read_bytes())
        if unsigned==base_sha:fail('relinked ARMv7 executable unchanged from UI43')
        binary=app/'Blender3GS';shutil.copy2(exe,binary)
        if sha(binary.read_bytes())!=unsigned:fail('copy mismatch before signing')
        plfile=app/'Info.plist';pl=plistlib.loads(plfile.read_bytes())
        pl['CFBundleVersion']='45'
        pl['CFBundleShortVersionString']='0.44.0'
        pl['CFBundleDisplayName']='Blender Py V44'
        pl['UIApplicationExitsOnSuspend']=False
        plfile.write_bytes(plistlib.dumps(pl,fmt=plistlib.FMT_XML))
        shutil.rmtree(app/'_CodeSignature',ignore_errors=True)
        (app/'CodeResources').unlink(missing_ok=True)
        run('sign UI44',['ldid','-S',binary])
        signed=sha(binary.read_bytes())
        partial=out.with_name(out.stem+'.partial.ipa')
        if partial.exists():fail('stale partial IPA, remove manually: '+str(partial))
        try:
            run('create UI44 IPA',['zip','-qry',partial,'Payload'],cwd=td)
            final_sha,new_roster=verify(partial,45)
            if final_sha!=signed or final_sha==base_sha:fail('signed executable validation failed')
            if roster!=new_roster:fail('IPA asset roster changed unexpectedly')
            with zipfile.ZipFile(base) as old,zipfile.ZipFile(partial) as new:
                for item in roster:
                    if item in (PFX+'Info.plist',PFX+'Blender3GS'):continue
                    if old.read(item)!=new.read(item):fail('unexpected non-binary modification: '+item)
            os.replace(partial,out)
        finally:partial.unlink(missing_ok=True)
    print('PASS: signed binary verified; unchanged Python/assets; version=45',flush=True)
    print('SUCCESS: UI44 IPA '+str(out),flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path.home()/'Downloads')
    ap.add_argument('--check-only',action='store_true')
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--package-only',action='store_true')
    a=ap.parse_args()
    if a.resume and a.package_only:fail('use only one of --resume/--package-only')
    root=a.root.expanduser().resolve()
    base=root/BASE;out=root/OUT
    baseline_sha,_=verify(base,44)
    if out.exists():fail('UI44 IPA already exists; run command --install-only')
    srcs={rel:root/'blender-ios6-target'/rel for rel in (DRAW,ICONS,OBJECT)}
    baks={rel:p.with_name(p.name+'.before-'+TAG) for rel,p in srcs.items()}
    patched=a.resume or a.package_only
    for rel,p in srcs.items():
        if not p.is_file():fail('missing Mac source: '+str(p))
        if patched and not baks[rel].is_file():fail('no UI44 backup; run normal command: '+str(baks[rel]))
        if not patched and baks[rel].exists():fail('UI44 backup exists; use --resume/--package-only instead')
    inputsrc={r:(baks[r] if patched else srcs[r]).read_text() for r in srcs}
    changes={DRAW:patch_draw(inputsrc[DRAW]),ICONS:patch_icons(inputsrc[ICONS]),OBJECT:patch_object(inputsrc[OBJECT])}
    if patched:
        for r,p in srcs.items():
            if p.read_text()!=changes[r]:fail('UI44 source differs from expected: '+str(p))
    print('PASS: UI43 exact structural anchors; baseline signed SHA256 '+baseline_sha,flush=True)
    print('PLAN: clipped icon quads + scoped region state + safe Camera/Lamp line crosses',flush=True)
    if a.check_only:
        print('CHECK ONLY: no changes made',flush=True);return
    build=root/'blender-ios6-build-python';exe=root/'Blender3GS-python-armv7';link=root/'blender-link-ios-python-v3.py'
    work=root/'blender-ios6-python'
    for p in (build/'build.ninja',exe,link):
        if not p.is_file():fail('missing prerequisite: '+str(p))
    if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):
        fail('DEVELOPER_DIR and IOS_SDKROOT are required')
    work.mkdir(exist_ok=True)
    if not patched:
        for r,p in srcs.items():
            shutil.copy2(p,baks[r]);p.write_text(changes[r]);print('BACKUP + PATCH:',p,flush=True)
    if not a.package_only:
        run('compile native affected modules',
            ['ninja','-C',build,'-j4','bf_windowmanager','bf_editor_interface','bf_editor_space_view3d'],work/'ui-v44-build.log')
        run('relink ARMv7',['python3',link],work/'ui-v44-link.log')
        run('verify ARMv7',['xcrun','lipo','-info',exe],work/'ui-v44-arch.log')
        if 'armv7' not in (work/'ui-v44-arch.log').read_text(errors='replace').lower():fail('wrong binary arch')
    else:
        logfile=work/'ui-v44-arch.log'
        if not logfile.is_file() or 'armv7' not in logfile.read_text(errors='replace').lower():
            fail('no UI44 ARMv7 verification; use --resume first')
    raw=exe.read_bytes()
    for marker in (b'Blender3GS UI44 FOCUS: scoped_region_GL=1',
                   b'Blender3GS UI44 FOCUS: icon_scissor=1',
                   b'Blender3GS UI44 FOCUS: safe_camera_lamp_crosses=1'):
        if marker not in raw:fail('ARMv7 executable missing patch marker: '+marker.decode())
    package(exe,base,out)
    print('NOT DEVICE-TESTED. If artifacts remain, UI43 rollback is untouched.',flush=True)

if __name__=='__main__':main()
