#!/usr/bin/env python3
"""UI41 experiment: cheap real Blender first-viewport (bbox), no second blank redraw,
late Python once, staged panels with bounded redraws. Exact live UI40 anchors required.

Never patches an unknown source. The native Blender binary is rebuilt and the UI40
IPA is used as the exact packaging baseline; the old IPA and original files remain.
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

TAG = 'BLENDER3GS_UI41_MEGA_BOOT_20260925'
WM = 'source/blender/windowmanager/intern/wm.c'
INIT = 'source/blender/windowmanager/intern/wm_init_exit.c'
DRAW = 'source/blender/windowmanager/intern/wm_draw.c'
BASE = 'Blender3GS-python-ui-v40-native-first-frame.ipa'
OUT = 'Blender3GS-python-ui-v41-mega-first-frame.ipa'
PFX = 'Payload/Blender3GS.app/'


def stop(msg):
    raise SystemExit('STOP: ' + msg)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def once(s, before, after, why):
    n = s.count(before)
    if n != 1:
        stop('%s: expected one exact anchor, found %d' % (why, n))
    return s.replace(before, after, 1)


def patch_wm(s):
    for tok in ('BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925',
                'UI37 STAGE: batch=', 'blender3gs_ui40_python_after_first_frame(C);',
                'blender3gs_ui40_python_started()',
                'blender3gs_ios6_boot_hide();'):
        if tok not in s:
            stop('wm.c does not match installed UI40: ' + tok)
    if TAG in s:
        stop('wm.c already UI41; use --resume')
    old = 'ui28_frame_ms() - ui40_native_frame_at >= 180.0) {'
    # Permit first C frame to reach CA through UIKit/GHOST before late Python.
    # Existing UI40 repeated an expensive blank-editor draw while waiting.
    new = ('ui28_frame_ms() - ui40_native_frame_at >= 33.0) {\n'
           '            syslog(LOG_WARNING, "Blender3GS UI41 MEGA: native_preview_committed_start_python");')
    s = once(s, old, new, 'start late Python after a short event-pump interval')
    # Exact existing UI40 gate is unique and precedes the normal WM handlers.
    gate = '''    blender3gs_ui40_python_after_first_frame(C);'''
    if s.count(gate) != 1:
        stop('unexpected UI40 late-Python call')
    # Avoid the redundant full draw between the first C viewport and late Python.
    # This is deliberately within WITH_IOS; the normal WM loop remains intact.
    pat = re.compile(r'(?m)^(?P<i>[ \t]*)if \(ui40_native_frame_at >= 0\.0 && blender3gs_ios6_is_active\(\) && !blender3gs_ui40_python_started\(\) && ui28_frame_ms\(\) - ui40_native_frame_at >= 33\.0\) \{')
    m = list(pat.finditer(s))
    if len(m) != 1:
        stop('unexpected UI40 late-Python condition')
    indent = m[0]['i']
    # Place this after the deferred-init `if` close, not in the brace body.
    # Anchor stable by exact generated tail (includes redraw loop) from UI40.
    tail = 'ui40_win->screen->do_draw = TRUE; } } }\n' + indent + '}\n#endif'
    if s.count(tail) != 1:
        stop('UI40 late-init gate end differs; refusing blind second-pass edit')
    s = once(s, tail,
             'ui40_win->screen->do_draw = TRUE; } } }\n' + indent + '}\n'
             + indent + '/* %s: do not draw a second blank/unfinished frame before Python. */\n' % TAG
             + indent + 'if (ui40_native_frame_at >= 0.0 && blender3gs_ios6_is_active() && !blender3gs_ui40_python_started()) {\n'
             + indent + '    continue; /* next iteration pumps the UIKit run loop */\n'
             + indent + '}\n#endif', 'suppress redundant preview redraw')
    # Avoid repeated full-screen invalidations during per-module UI37 registration.
    # Redraw at first meaningful milestone and when module queue is fully exhausted.
    pat = re.compile(r'if \(ui37_step % 4 == 0 \|\| ui37_step == (\d+)\) \{')
    matches = list(pat.finditer(s))
    if len(matches) != 1:
        stop('UI37 staging redraw throttle changed')
    total = matches[0].group(1)
    s = pat.sub('if (ui37_step == 8 || ui37_step == %s) {' % total, s, count=1)
    return s


def patch_init(s):
    for tok in ('BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925',
                'void blender3gs_ui40_python_after_first_frame(bContext *C)',
                'ED_preview_init_dbase();', 'ui30_init_stage("history_done"'):
        if tok not in s:
            stop('wm_init_exit.c does not match UI40: ' + tok)
    if TAG in s:
        stop('wm_init_exit.c already UI41; use --resume')
    # Database preview allocation was measured between UI_init and 'history_done'
    # at ~0.3s even when WM_read_history was disabled in UI40. Delaying it is
    # an experiment; it is restored on the Blender main thread before Python.
    old = '\tED_preview_init_dbase();'
    new = '''#ifndef WITH_IOS
\tED_preview_init_dbase();
#else
    /* %s: not needed by the early C-only Viewport. */
    syslog(LOG_WARNING, "Blender3GS UI41 MEGA: editor_preview_db_deferred");
#endif''' % TAG
    s = once(s, old, new, 'defer first-frame-unneeded preview database')
    old = '    BPY_context_set(C);\n    BPY_python_start(ui40_argc, ui40_argv);'
    new = '''    /* UI41: allocate editor previews after the first native frame, before
     * Python startup and all panel registrations. Stay on the main thread. */
    ED_preview_init_dbase();
    syslog(LOG_WARNING, "Blender3GS UI41 MEGA: preview_db_ready_after_first_frame");
    BPY_context_set(C);
    BPY_python_start(ui40_argc, ui40_argv);'''
    s = once(s, old, new, 'late preview database init')
    return s


def patch_draw(s):
    for tok in ('BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925',
                'first_frame_skip_area=',
                'wm_method_draw_full(bContext *C, wmWindow *win)',
                'ED_region_do_draw(C, ar);'):
        if tok not in s:
            stop('wm_draw.c does not match UI40: ' + tok)
    if TAG in s:
        stop('wm_draw.c already UI41; use --resume')
    # Make the first genuine viewport rendering cheap. Only the FIRST full pass
    # before Python uses bounding-box geometry. All user draw settings are
    # restored immediately, and the full viewport is tagged after Python.
    inc = '#include "DNA_view3d_types.h"'
    s = once(s, inc, inc + '\n#ifdef WITH_IOS\n#include "DNA_object_types.h"\n#endif', 'legacy drawtype constant')
    first = s.index('static void wm_method_draw_full(bContext *C, wmWindow *win)')
    last = s.index('/****************** draw overlap all', first)
    before_full, full, after_full = s[:first], s[first:last], s[last:]
    s = full
    old = '''\tfor (sa = screen->areabase.first; sa; sa = sa->next) {
#ifdef WITH_IOS
        /* BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925: first real viewport'''
    new = '''\tfor (sa = screen->areabase.first; sa; sa = sa->next) {
#ifdef WITH_IOS
        /* BLENDER3GS_UI41_MEGA_BOOT_20260925: C-only bounding-box preview; restore drawtype before return. */
        View3D *ui41_v3d = NULL;
        short ui41_saved_drawtype = 0;
        /* BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925: first real viewport'''
    s = once(s, old, new, 'first area local preview state')
    old = '''\t\tCTX_wm_area_set(C, sa);

\t\tfor (ar = sa->regionbase.first; ar; ar = ar->next) {'''
    new = '''#ifdef WITH_IOS
        if (!blender3gs_ui40_python_started() && sa->spacetype == SPACE_VIEW3D &&
            sa->spacedata.first) {
            ui41_v3d = (View3D *)sa->spacedata.first;
            ui41_saved_drawtype = ui41_v3d->drawtype;
            ui41_v3d->drawtype = OB_BOUNDBOX;
            syslog(LOG_WARNING, "Blender3GS UI41 MEGA: bbox_preview_begin");
        }
#endif
\t\tCTX_wm_area_set(C, sa);

\t\tfor (ar = sa->regionbase.first; ar; ar = ar->next) {'''
    s = once(s, old, new, 'first full area draw call')
    old = '''\t\tw m_area_mark_invalid_backbuf(sa);'''
    # Not a textual anchor; place restoration before *first* real call.
    old = '''\t\twm_area_mark_invalid_backbuf(sa);
\t\tCTX_wm_area_set(C, NULL);'''
    new = '''#ifdef WITH_IOS
        if (ui41_v3d) {
            ui41_v3d->drawtype = ui41_saved_drawtype;
            syslog(LOG_WARNING, "Blender3GS UI41 MEGA: bbox_preview_end");
        }
#endif
\t\twm_area_mark_invalid_backbuf(sa);
\t\tCTX_wm_area_set(C, NULL);'''
    # This sequence may exist in multiple drawing methods; ensure only first.
    s = once(s, old, new, 'restore original viewport shading in full method')
    return before_full + s + after_full


def verify_base(path):
    if not path.is_file():
        stop('UI40 IPA missing: %s. Previous successful UI40 is required.' % path)
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            stop('UI40 IPA failed CRC')
        names = z.namelist()
        if len(names) != len(set(names)) or any(n.startswith('/') or '..' in Path(n).parts for n in names):
            stop('unsafe or duplicated UI40 IPA entries')
        for part in ('Blender3GS', 'Info.plist',
                     '2.64/scripts/startup/bl_ui/__init__.py',
                     '2.64/scripts/modules/bpy/utils.py'):
            if PFX + part not in names:
                stop('baseline missing ' + part)
        meta = plistlib.loads(z.read(PFX + 'Info.plist'))
        if (str(meta.get('CFBundleVersion')) != '41' or
                meta.get('CFBundleIdentifier') != 'io.arutiunio.blender3gs.python' or
                meta.get('UIApplicationExitsOnSuspend') is not False):
            stop('expected UI40 version 41 / same bundle ID / suspend disabled')
        return sha(z.read(PFX + 'Blender3GS'))


def run(stage, cmd, logfile=None, cwd=None):
    print('===', stage, '===', flush=True)
    print('COMMAND:', ' '.join(str(x) for x in cmd), flush=True)
    if logfile:
        with open(logfile, 'w') as f:
            result = subprocess.run([str(x) for x in cmd], cwd=cwd,
                                    stdout=f, stderr=subprocess.STDOUT)
        if result.returncode:
            stop('%s failed (exit %d). Log: %s\n%s' %
                 (stage, result.returncode, logfile,
                  Path(logfile).read_text(errors='replace')[-10000:]))
        print('PASS:', logfile, flush=True)
    else:
        subprocess.run([str(x) for x in cmd], cwd=cwd, check=True)


def package(root, exe, out, base):
    for dep in ('unzip', 'zip', 'ldid'):
        if not shutil.which(dep):
            stop('missing command: ' + dep)
    with tempfile.TemporaryDirectory(prefix='blender3gs-ui41-') as temp:
        work = Path(temp)
        run('unpack exact UI40 IPA', ['unzip', '-q', base, '-d', work])
        app = work / 'Payload' / 'Blender3GS.app'
        binary = app / 'Blender3GS'
        shutil.copy2(exe, binary)
        plistfile = app / 'Info.plist'
        info = plistlib.loads(plistfile.read_bytes())
        info['CFBundleVersion'] = '42'
        info['CFBundleShortVersionString'] = '0.41.0'
        info['CFBundleDisplayName'] = 'Blender Py Mega'
        info['UIApplicationExitsOnSuspend'] = False
        plistfile.write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_XML))
        shutil.rmtree(app / '_CodeSignature', ignore_errors=True)
        (app / 'CodeResources').unlink(missing_ok=True)
        run('sign binary', ['ldid', '-S', binary])
        partial = out.with_suffix('.partial.ipa')
        if partial.exists():
            stop('existing partial IPA: ' + str(partial))
        try:
            run('package UI41', ['zip', '-qry', partial, 'Payload'], cwd=work)
            with zipfile.ZipFile(partial) as output:
                if output.testzip():
                    stop('output CRC mismatch')
                result = plistlib.loads(output.read(PFX + 'Info.plist'))
                if (str(result.get('CFBundleVersion')) != '42' or
                        result.get('CFBundleIdentifier') != 'io.arutiunio.blender3gs.python' or
                        result.get('UIApplicationExitsOnSuspend') is not False):
                    stop('output IPA identity/version/suspend mismatch')
                if sha(output.read(PFX + 'Blender3GS')) != sha(binary.read_bytes()):
                    stop('packaged executable differs')
                with zipfile.ZipFile(base) as original:
                    if set(original.namelist()) != set(output.namelist()):
                        stop('unexpected IPA file roster change')
                    for rel in ('2.64/scripts/startup/bl_ui/__init__.py',
                                '2.64/scripts/startup/bl_operators/__init__.py',
                                '2.64/scripts/modules/bpy/utils.py'):
                        if output.read(PFX + rel) != original.read(PFX + rel):
                            stop('Python source changed unexpectedly: ' + rel)
            os.replace(partial, out)
        finally:
            partial.unlink(missing_ok=True)
    print('SUCCESS: UI41 IPA', out, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / 'Downloads')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    source = root / 'blender-ios6-target'
    build = root / 'blender-ios6-build-python'
    work = root / 'blender-ios6-python'
    exe = root / 'Blender3GS-python-armv7'
    link = root / 'blender-link-ios-python-v3.py'
    base = root / BASE
    out = root / OUT
    paths = {WM: source / WM, INIT: source / INIT, DRAW: source / DRAW}
    backups = {k: v.with_name(v.name + '.before-' + TAG) for k, v in paths.items()}
    baseline_sha = verify_base(base)
    if out.exists():
        stop('UI41 IPA already exists; use shell --install-only')
    for name, path in paths.items():
        if not path.is_file():
            stop('missing source: ' + str(path))
        if args.resume and not backups[name].is_file():
            stop('--resume has no backup: %s; first run must use regular command' % backups[name])
        if not args.resume and backups[name].exists():
            stop('pre-existing UI41 backup: ' + str(backups[name]))
    src = {k: (backups[k] if args.resume else path).read_text()
           for k, path in paths.items()}
    transformed = {WM: patch_wm(src[WM]), INIT: patch_init(src[INIT]), DRAW: patch_draw(src[DRAW])}
    if args.resume:
        for k, path in paths.items():
            if path.read_text() != transformed[k]:
                stop('--resume source differs from verified UI41 patch: ' + k)
    print('PASS: verified UI40 native C preview, deferred Python, UI37 staging, and UI40 IPA', flush=True)
    print('BASE UI40 MACH-O SHA256:', baseline_sha, flush=True)
    print('PLAN: actual C bbox first frame, shorter handoff, no redundant second frame, defer preview database', flush=True)
    if args.check_only:
        print('CHECK ONLY: all source files unchanged', flush=True)
        return
    for path in (build / 'build.ninja', exe, link):
        if not path.is_file():
            stop('missing build prerequisite ' + str(path))
    if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):
        stop('DEVELOPER_DIR / IOS_SDKROOT not configured')
    work.mkdir(exist_ok=True)
    if not args.resume:
        for name, path in paths.items():
            shutil.copy2(path, backups[name])
            path.write_text(transformed[name])
            print('BACKUP + PATCH:', path, flush=True)
        oldbin = work / ('Blender3GS-before-ui41-' + sha(exe.read_bytes())[:12] + '-armv7')
        if not oldbin.exists():
            shutil.copy2(exe, oldbin)
    run('compile native ARMv7', ['ninja', '-C', build, '-j4', 'bf_windowmanager'],
        work / 'ui-v41-build.log')
    run('relink ARMv7', ['python3', link], work / 'ui-v41-link.log')
    run('lipo ARMv7', ['xcrun', 'lipo', '-info', exe], work / 'ui-v41-arch.log')
    if 'armv7' not in (work / 'ui-v41-arch.log').read_text().lower():
        stop('relinked binary is not ARMv7')
    if sha(exe.read_bytes()) == baseline_sha:
        stop('binary unchanged from UI40 after supposed native patch')
    package(root, exe, out, base)
    print('NOTE: this experimental package has NOT been run on physical iPhone by this script.', flush=True)


if __name__ == '__main__':
    main()
