#!/usr/bin/env python3
"""UI43 diagnostic native visual patch for Blender 2.64 / iPhone 3GS.

Exact UI41 input required. It preserves UI41 first native Viewport, late Python,
UI39 3D Core and existing CPU picking. Separately tests suspected camera/lamp
viewport gizmos and implements a per-icon 16x16 texture fallback for UI37's
broken glDrawPixels path. Do not use on a different source tree.
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

TAG = 'BLENDER3GS_UI43_VISUAL_DIAGNOSTIC_20260925'
DRAW = 'source/blender/windowmanager/intern/wm_draw.c'
ICONS = 'source/blender/editors/interface/interface_icons.c'
OBJECT = 'source/blender/editors/space_view3d/drawobject.c'
BASE = 'Blender3GS-python-ui-v41-mega-first-frame.ipa'
OUT = 'Blender3GS-python-ui-v43-visual-diagnostic.ipa'
PFX = 'Payload/Blender3GS.app/'


def stop(s):
    raise SystemExit('STOP: ' + s)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def once(s, old, new, desc):
    n = s.count(old)
    if n != 1:
        stop('%s: expected one exact anchor, found %d' % (desc, n))
    return s.replace(old, new, 1)


def patch_draw(s):
    """Remove UI41's temporary bbox mutation, do not touch fast C frame."""
    for x in ('BLENDER3GS_UI41_MEGA_BOOT_20260925',
              'BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925',
              'ui41_v3d->drawtype = OB_BOUNDBOX;',
              'ui41_v3d->drawtype = ui41_saved_drawtype;'):
        if x not in s:
            stop('wm_draw.c is not UI41: ' + x)
    if TAG in s or 'BLENDER3GS_UI42_SAFE_NATIVE_SHADE_20260925' in s:
        stop('wm_draw.c already modified by UI42/UI43; use the correct UI41 backup')
    s = once(s, 'ui41_v3d->drawtype = OB_BOUNDBOX;',
             '/* %s: no temporary viewport drawtype mutation. */' % TAG,
             'preserve user-selected viewport drawtype')
    s = once(s, 'Blender3GS UI41 MEGA: bbox_preview_begin',
             'Blender3GS UI43 VIS: original_viewport_drawtype', 'first-frame log')
    s = once(s, 'Blender3GS UI41 MEGA: bbox_preview_end',
             'Blender3GS UI43 VIS: original_viewport_drawtype_restored', 'restore log')
    return s


def patch_object(s):
    """Bypass *only* camera and lamp Viewport gizmo geometry at draw_object entry.

    Camera and Lamp remain in .blend, Outliner, rendering, and CPU-picking data.
    This is a diagnostic isolation of a white-triangle / frame artifact; it
    intentionally does not provide replacement camera/lamp wireframe gizmos.
    """
    if TAG in s:
        stop('drawobject.c already UI43')
    fn = re.compile(r'(?m)^void\s+draw_object\s*\(([^;{}]*)\)\s*\{')
    matches = list(fn.finditer(s))
    if len(matches) != 1:
        stop('drawobject.c: cannot uniquely identify main draw_object function (%d matches). Please upload this C file.' % len(matches))
    params = matches[0].group(1)
    for x in ('Scene', 'ARegion', 'View3D', 'Base', 'base'):
        if x not in params:
            stop('draw_object signature differs; missing ' + x)
    # C99 is supported by the existing iOS clang toolchain. Insert before any
    # renderer GL state changes; early return therefore needs no state unwind.
    new = '''\n#ifdef WITH_IOS
    /* %s: isolate legacy GL4ES camera/lamp gizmo rasterization.
     * Do NOT delete/disable actual scene objects, and never modify drawtype. */
    if (base && base->object) {
        const short ui43_type = base->object->type;
        if (ui43_type == OB_CAMERA || ui43_type == OB_LAMP) {
            static int ui43_camera_logged = 0, ui43_lamp_logged = 0;
            if (ui43_type == OB_CAMERA && !ui43_camera_logged++)
                syslog(LOG_WARNING, "Blender3GS UI43 VIS: camera_viewport_helper_skipped");
            if (ui43_type == OB_LAMP && !ui43_lamp_logged++)
                syslog(LOG_WARNING, "Blender3GS UI43 VIS: lamp_viewport_helper_skipped");
            return;
        }
    }
#endif
''' % TAG
    at = matches[0].end()
    s = s[:at] + new + s[at:]
    if '#include <syslog.h>' not in s:
        s = '#ifdef WITH_IOS\n#include <syslog.h>\n#endif\n' + s
    return s


def patch_icons(s):
    """UI37 CPU buffer -> one lazy cached 16x16 GL texture per visible stock icon.

    Reuses Blender's existing textured quad rasterizer. No new GLSL/GL4ES ABI.
    This is separate from dynamic image previews and existing vector icons.
    """
    for x in ('ICON_TYPE_BUFFER', 'ICON_TYPE_TEXTURE', 'void UI_icons_free_drawinfo',
              'static void icon_draw_texture(', 'static void icon_draw_size(',
              'BLENDER3GS_UI37_STAGE_REAL_UI_ICON_BUFFER_20260924',
              'Blender3GS UI37 ICON: cpu_buffer_no_atlas=1'):
        if x not in s:
            stop('interface_icons.c not the working UI37 buffer path: ' + x)
    if TAG in s:
        stop('interface_icons.c already UI43')
    # Avoid evaluating old->new with an interpolated source substring: user tree
    # may have CRLF/trailing spacing, but require a unique exact declaration.
    m = re.search(r'typedef struct IconImage\s*\{(?P<body>[^}]*)\}\s*IconImage\s*;', s)
    if not m or len(re.findall(r'typedef struct IconImage\s*\{', s)) != 1:
        stop('IconImage declaration not unique')
    body = m['body']
    if len(re.findall(r'unsigned\s+int\s*\*\s*rect\s*;', body)) != 1:
        stop('IconImage rect declaration changed')
    body2 = re.sub(r'(unsigned\s+int\s*\*\s*rect\s*;)',
                   r'\1\n#ifdef WITH_IOS\n    GLuint ui43_tex; /* ' + TAG + ' */\n#endif',
                   body, count=1)
    s = s[:m.start('body')] + body2 + s[m.end('body'):]
    # Existing constructor allocates IconImage with MEM_mallocN (NOT calloc).
    anchor = 'iimg->h = size;'
    s = once(s, anchor,
             anchor + '\n#ifdef WITH_IOS\n        iimg->ui43_tex = 0;\n#endif',
             'zero-initialize texture handle')
    # Delete each cached texture during the existing buffer icon destructor.
    m = re.search(r'void UI_icons_free_drawinfo\s*\([^)]*\)\s*\{', s)
    if not m:
        stop('no icon destructor')
    sub = s[m.end():]
    old = 'MEM_freeN(di->data.buffer.image->rect);'
    if sub.count(old) != 1:
        stop('cannot uniquely find original icon buffer destructor')
    s = s[:m.end()] + sub.replace(old,
             '''#ifdef WITH_IOS
                if (di->data.buffer.image->ui43_tex)
                    glDeleteTextures(1, &di->data.buffer.image->ui43_tex);
#endif
                MEM_freeN(di->data.buffer.image->rect);''', 1)
    # Replace *only* the stock ICON_TYPE_BUFFER branch. Keep preview and vector
    # paths unchanged and preserve Blender's original quad positioning code.
    if s.count('static void icon_draw_size(') != 1:
        stop('cannot uniquely find icon_draw_size implementation')
    old = 'icon_draw_rect(x, y, w, h, aspect, iimg->w, iimg->h, iimg->rect, alpha, rgb, is_preview);'
    if s.count(old) != 1:
        stop('stock bitmap icon draw call changed')
    new = '''#ifdef WITH_IOS
        /* %s: 16x16 on-demand texture, not a 1024x1024 atlas
         * and not glDrawPixels (which is unreliable on this GLES bridge). */
        if (!iimg->ui43_tex) {
            GLuint tex = 0;
            GLenum err;
            int drained = 0;
            while (drained++ < 8 && glGetError() != GL_NO_ERROR) { }
            glGenTextures(1, &tex);
            if (tex) {
                glBindTexture(GL_TEXTURE_2D, tex);
                glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, iimg->w, iimg->h, 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, iimg->rect);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
                err = glGetError();
                glBindTexture(GL_TEXTURE_2D, 0);
                if (err == GL_NO_ERROR) {
                    static int ui43_icon_reported = 0;
                    iimg->ui43_tex = tex;
                    if (ui43_icon_reported++ < 3)
                        syslog(LOG_WARNING, "Blender3GS UI43 VIS: tiny_icon_texture_ok id=%%u size=%%dx%%d",
                               (unsigned)tex, iimg->w, iimg->h);
                }
                else {
                    static int ui43_icon_error_reported = 0;
                    if (ui43_icon_error_reported++ < 3)
                        syslog(LOG_WARNING, "Blender3GS UI43 VIS: tiny_icon_texture_error 0x%%x", (unsigned)err);
                    glDeleteTextures(1, &tex);
                }
            }
        }
        if (iimg->ui43_tex) {
            IconTexture old_texture = icongltex;
            icongltex.id = iimg->ui43_tex;
            icongltex.w = iimg->w; icongltex.h = iimg->h;
            icongltex.invw = 1.0f / (float)iimg->w;
            icongltex.invh = 1.0f / (float)iimg->h;
            icon_draw_texture(x, y, (float)w, (float)h, 0, 0,
                              iimg->w, iimg->h, alpha, rgb);
            icongltex = old_texture;
        }
        /* If GL allocation failed, leave the icon blank rather than calling
         * a known-broken glDrawPixels path (which can corrupt other pixels). */
#else
        icon_draw_rect(x, y, w, h, aspect, iimg->w, iimg->h, iimg->rect, alpha, rgb, is_preview);
#endif''' % TAG
    s = once(s, old, new, 'replace only stock bitmap icon path')
    return s


def verify_ipa(path, expected):
    if not path.is_file():
        stop('missing baseline IPA: ' + str(path))
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad: stop('corrupted IPA member ' + bad)
        names = z.namelist()
        if len(names) != len(set(names)) or any(n.startswith('/') or '..' in Path(n).parts for n in names):
            stop('unsafe/duplicated IPA members')
        for rel in ('Info.plist', 'Blender3GS', '2.64/scripts/startup/bl_ui/__init__.py'):
            if PFX + rel not in names: stop('missing IPA member ' + rel)
        meta = plistlib.loads(z.read(PFX + 'Info.plist'))
        if (str(meta.get('CFBundleVersion')) != str(expected) or
                meta.get('CFBundleIdentifier') != 'io.arutiunio.blender3gs.python' or
                meta.get('UIApplicationExitsOnSuspend') is not False):
            stop('IPA is not expected v%s identity/suspend: %s' % (expected, path))
        return sha(z.read(PFX+'Blender3GS')), set(names)


def run(label, cmd, log=None, cwd=None):
    print('=== ' + label + ' ===', flush=True)
    print('COMMAND:', ' '.join(map(str, cmd)), flush=True)
    if log:
        with log.open('w') as f:
            r = subprocess.run(list(map(str,cmd)), cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
        if r.returncode:
            stop('%s exit=%d; log=%s\n%s' % (label, r.returncode, log, log.read_text(errors='replace')[-12000:]))
    else:
        r = subprocess.run(list(map(str,cmd)), cwd=cwd)
        if r.returncode: stop('%s exit=%d' % (label,r.returncode))


def package(exe, base, out):
    for x in ('zip','unzip','ldid'):
        if not shutil.which(x): stop('missing host tool ' + x)
    oldsha, roster = verify_ipa(base, 42)
    with tempfile.TemporaryDirectory(prefix='Blender3GS-ui43-') as td:
        tmp = Path(td)
        run('unpack verified UI41', ['unzip','-q',base,'-d',tmp])
        app = tmp/'Payload'/'Blender3GS.app'
        shutil.copy2(exe,app/'Blender3GS')
        plist = app/'Info.plist'
        info = plistlib.loads(plist.read_bytes())
        info['CFBundleVersion']='44'
        info['CFBundleShortVersionString']='0.43.0'
        info['CFBundleDisplayName']='Blender Py V43'
        info['UIApplicationExitsOnSuspend']=False
        plist.write_bytes(plistlib.dumps(info,fmt=plistlib.FMT_XML))
        shutil.rmtree(app/'_CodeSignature',ignore_errors=True)
        (app/'CodeResources').unlink(missing_ok=True)
        run('sign UI43',['ldid','-S',app/'Blender3GS'])
        partial = out.with_name(out.stem+'.partial.ipa')
        if partial.exists(): stop('stale partial IPA ' + str(partial))
        try:
            run('package UI43',['zip','-qry',partial,'Payload'],cwd=tmp)
            newsha,newroster=verify_ipa(partial,44)
            if newsha != sha(exe.read_bytes()) or newsha == oldsha:
                stop('packaged binary incorrect or unchanged')
            if roster != newroster:stop('asset roster changed')
            with zipfile.ZipFile(base) as b, zipfile.ZipFile(partial) as o:
                for rel in roster:
                    if rel in (PFX+'Blender3GS',PFX+'Info.plist'): continue
                    if b.read(rel)!=o.read(rel):stop('unexpected asset/Python change '+rel)
            os.replace(partial,out)
        finally:partial.unlink(missing_ok=True)
    print('SUCCESS: UI43 IPA: '+str(out),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path.home()/'Downloads')
    ap.add_argument('--check-only',action='store_true')
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    root=args.root.expanduser().resolve()
    base=root/BASE;out=root/OUT
    oldsha,_=verify_ipa(base,42)
    if out.exists():stop('UI43 IPA already exists; use --install-only')
    files={rel:root/'blender-ios6-target'/rel for rel in (DRAW,ICONS,OBJECT)}
    backups={rel:p.with_name(p.name+'.before-'+TAG) for rel,p in files.items()}
    for rel,p in files.items():
        if not p.is_file():stop('missing source '+str(p))
        if args.resume and not backups[rel].is_file():stop('no UI43 backup; regular command is needed: '+str(backups[rel]))
        if not args.resume and backups[rel].exists():stop('UI43 backup already exists: use --resume only if all patched files match')
    source={rel:(backups[rel] if args.resume else p).read_text() for rel,p in files.items()}
    output={DRAW:patch_draw(source[DRAW]),ICONS:patch_icons(source[ICONS]),OBJECT:patch_object(source[OBJECT])}
    if args.resume:
        for rel,p in files.items():
            if p.read_text()!=output[rel]:stop('source modified since UI43 patch; refusing resume: '+str(p))
    print('PASS: UI41 + UI37 GPU icon buffer anchors and isolated draw_object signature',flush=True)
    print('BASE UI41 binary SHA256:',oldsha,flush=True)
    print('PLAN: keep native first frame; original shading; isolate Camera/Lamp gizmos; lazy 16x16 icon textures',flush=True)
    if args.check_only:
        print('CHECK ONLY: no source changed',flush=True)
        return
    build=root/'blender-ios6-build-python'; exe=root/'Blender3GS-python-armv7'
    work=root/'blender-ios6-python';link=root/'blender-link-ios-python-v3.py'
    for p in (build/'build.ninja',exe,link):
        if not p.is_file():stop('missing build prerequisite '+str(p))
    if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):
        stop('DEVELOPER_DIR and IOS_SDKROOT required')
    work.mkdir(exist_ok=True)
    if not args.resume:
        # All three patches are calculated/validated before touching any file.
        for rel,p in files.items():
            shutil.copy2(p,backups[rel]);p.write_text(output[rel]);print('BACKUP + PATCH:',p,flush=True)
    run('compile window manager / interface / view3d',
        ['ninja','-C',build,'-j4','bf_windowmanager','bf_editor_interface','bf_editor_space_view3d'],
        work/'ui-v43-build.log')
    run('relink ARMv7',['python3',link],work/'ui-v43-link.log')
    run('verify ARMv7',['xcrun','lipo','-info',exe],work/'ui-v43-arch.log')
    if 'armv7' not in (work/'ui-v43-arch.log').read_text().lower():stop('non-ARMv7 output')
    if sha(exe.read_bytes())==oldsha:stop('native executable unchanged')
    package(exe,base,out)
    print('NOTE: device visual results must be checked; UI43 is a diagnostic, not verified hardware fix.',flush=True)

if __name__=='__main__':main()
