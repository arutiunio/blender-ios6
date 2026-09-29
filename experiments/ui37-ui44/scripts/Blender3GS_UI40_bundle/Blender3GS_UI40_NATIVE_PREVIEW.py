#!/usr/bin/env python3
"""UI40 experiment: native Blender 3D first frame BEFORE Python startup.

Intentionally risky: does NOT claim instant full editor or background persistence.
Requires UI37 native sources + UI39 Core IPA and build environment on user's Mac.
Does not remove Python or project files. Backs up sources and Mach-O, refuses mismatch.
"""
import argparse, hashlib, os, plistlib, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

TAG='BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925'
WM='source/blender/windowmanager/intern/wm.c'
INIT='source/blender/windowmanager/intern/wm_init_exit.c'
DRAW='source/blender/windowmanager/intern/wm_draw.c'
BASE='Blender3GS-python-ui-v39-3d-core.ipa'
OUTPUT='Blender3GS-python-ui-v40-native-first-frame.ipa'
PFX='Payload/Blender3GS.app/'

def stop(msg): raise SystemExit('STOP: '+msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def once(s,a,b,why):
    n=s.count(a)
    if n!=1:stop('%s: expected exactly one anchor, found %d'%(why,n))
    return s.replace(a,b,1)

def patch_init(s):
    if TAG in s:stop('WM init already UI40; use --resume')
    for token in ('BLENDER3GS_UI30_BOOT_PHASES_IDLE_20260924', 'BPY_python_start(argc, argv);', 'BPY_driver_reset();', 'BPY_modules_load_user(C);'):
        if token not in s:stop('WM init lacks expected '+token)
    # Keep the existing WITH_PYTHON conditional and all instrumented statements;
    # defer only the original Python block. On desktop, behavior is unchanged.
    a='''\tBPY_context_set(C); /* necessary evil */
\tBPY_python_start(argc, argv);'''
    b='''#ifdef WITH_IOS
    /* %s: hold arguments until first native frame has been presented. */
    blender3gs_ui40_save_python_args(argc, argv);
    syslog(LOG_WARNING, "Blender3GS UI40 FAST: python_deferred_until_native_frame");
#else
\tBPY_context_set(C); /* necessary evil */
\tBPY_python_start(argc, argv);
#endif'''%TAG
    s=once(s,a,b,'defer Python start')
    # The original optional UI30 timing is still valid, but now a deferred
    # marker rather than completion. Avoid misleading old measurement name.
    s=once(s,'ui30_init_stage("python_start_done", ui30_t0, &ui30_previous);',
           'ui30_init_stage("python_deferred", ui30_t0, &ui30_previous);','timing label')
    a='''\tBPY_driver_reset();
\tBPY_app_handlers_reset(FALSE); /* causes addon callbacks to be freed [#28068],
\t                                * but this is actually what we want. */
\tBPY_modules_load_user(C);'''
    b='''#ifndef WITH_IOS
\tBPY_driver_reset();
\tBPY_app_handlers_reset(FALSE); /* causes addon callbacks to be freed [#28068],
\t                                * but this is actually what we want. */
\tBPY_modules_load_user(C);
#endif'''
    s=once(s,a,b,'defer Python-dependent callbacks')
    s=once(s,'ui30_init_stage("python_scripts_done", ui30_t0, &ui30_previous);',
           'ui30_init_stage("python_scripts_deferred", ui30_t0, &ui30_previous);','scripts timing label')
    s=once(s,'\tWM_read_history();', '#ifndef WITH_IOS\n\tWM_read_history(); /* UI40 skips recent-file history on 3GS. */\n#endif', 'skip disk history on iOS')
    a='''/* only called once, for startup */
void WM_init(bContext *C, int argc, const char **argv)'''
    b='''#if defined(WITH_IOS) && defined(WITH_PYTHON)
/* %s: no secondary interpreter, no background thread, no extra GLES context.
 * Python is initialized on the Blender main thread after the first native draw. */
static int ui40_argc = 0;
static const char **ui40_argv = NULL;
static int ui40_python_ready_flag = 0;

static void blender3gs_ui40_save_python_args(int argc, const char **argv)
{
    int i;
    if (ui40_argv || ui40_python_ready_flag) return;
    if (argc < 0 || argc > 128) abort();
    ui40_argc = argc;
    ui40_argv = MEM_callocN(sizeof(*ui40_argv) * (argc + 1), "ui40 saved argv");
    if (!ui40_argv) abort();
    for (i = 0; i < argc; i++)
        ui40_argv[i] = BLI_strdup((argv && argv[i]) ? argv[i] : "");
}

int blender3gs_ui40_python_started(void) { return ui40_python_ready_flag; }
void blender3gs_ui40_python_after_first_frame(bContext *C)
{
    int i;
    double t0;
    if (ui40_python_ready_flag || !ui40_argv) return;
    t0 = ui30_init_time();
    syslog(LOG_WARNING, "Blender3GS UI40 FAST: late_python_begin");
    BPY_context_set(C);
    BPY_python_start(ui40_argc, ui40_argv);
    BPY_driver_reset();
    BPY_app_handlers_reset(FALSE);
    BPY_modules_load_user(C);
    ui40_python_ready_flag = 1;
    for (i = 0; i < ui40_argc; i++) MEM_freeN((void *)ui40_argv[i]);
    MEM_freeN((void *)ui40_argv);
    ui40_argv = NULL;
    syslog(LOG_WARNING, "Blender3GS UI40 FAST: late_python_complete_ms=%%.1f", ui30_init_time() - t0);
}
#elif defined(WITH_IOS)
static void blender3gs_ui40_save_python_args(int argc, const char **argv)
{ (void)argc; (void)argv; }
#endif

/* only called once, for startup */
void WM_init(bContext *C, int argc, const char **argv)'''%TAG
    s=once(s,a,b,'late init helper')
    return s

def patch_wm(s):
    if TAG in s:stop('WM already UI40; use --resume')
    for token in ('BLENDER3GS_UI37_STAGE_REAL_UI_ICON_BUFFER_20260924',
                  'blender3gs_ios6_boot_hide();','ui28_first_frames'):
        if token not in s:stop('WM lacks expected '+token)
    # The UI37 stage worker must not execute before the interpreter exists.
    p=r'if \(ui28_first_frames && ui37_step < (\d+) && blender3gs_ios6_is_active\(\)\)'
    match=list(re.finditer(p,s))
    if len(match)!=1:stop('UI37 stage gate differs; refusing unsafe patch')
    s=re.sub(p,lambda m:'if (ui28_first_frames && ui37_step < '+m.group(1)+
             ' && blender3gs_ios6_is_active() && blender3gs_ui40_python_started())',s,count=1)
    a='''#include "BPY_extern.h"
#endif'''
    b='''#include "BPY_extern.h"
#endif
#ifdef WITH_IOS
/* %s: implemented in wm_init_exit.c, never a Python worker. */
extern int blender3gs_ui40_python_started(void);
extern void blender3gs_ui40_python_after_first_frame(bContext *C);
#endif'''%TAG
    s=once(s,a,b,'deferred Python declarations')
    a='''void WM_main(bContext *C)
{'''
    b='''void WM_main(bContext *C)
{
#ifdef WITH_IOS
    double ui40_native_frame_at = -1.0;
#endif'''
    s=once(s,a,b,'first-frame state')
    # On the *next* pass the GHOST event pump has run, allowing CoreAnimation
    # to commit the early frame before the blocking late Python import.
    p=r'(?m)^([ \t]*)wm_window_process_events\(C\);[ \t]*$'
    matches=list(re.finditer(p,s))
    if len(matches)!=1:stop('cannot locate unique GHOST event pump')
    m=matches[0];indent=m.group(1)
    injection=(indent+'wm_window_process_events(C);\n'
      +'#ifdef WITH_IOS\n'
      +indent+'if (ui40_native_frame_at >= 0.0 && blender3gs_ios6_is_active() && !blender3gs_ui40_python_started() && ui28_frame_ms() - ui40_native_frame_at >= 180.0) {\n'
      +indent+'    blender3gs_ui40_python_after_first_frame(C);\n'
      +indent+'    { wmWindowManager *ui40_wm = CTX_wm_manager(C); wmWindow *ui40_win; for (ui40_win = ui40_wm->windows.first; ui40_win; ui40_win = ui40_win->next) { if (ui40_win->screen) { ScrArea *ui40_area; for (ui40_area = ui40_win->screen->areabase.first; ui40_area; ui40_area = ui40_area->next) ED_area_tag_redraw(ui40_area); ui40_win->screen->do_draw = TRUE; } } }\n'
      +indent+'}\n'
      +'#endif')
    s=s[:m.start()]+injection+s[m.end():]
    p=r'(?m)^([ \t]*)wm_draw_update\(C\);[ \t]*$'
    matches=list(re.finditer(p,s))
    if len(matches)!=1:stop('cannot locate unique draw in WM_main')
    m=matches[0];indent=m.group(1)
    injection=indent+'wm_draw_update(C);\n#ifdef WITH_IOS\n'+indent+'if (ui40_native_frame_at < 0.0) { ui40_native_frame_at = ui28_frame_ms(); syslog(LOG_WARNING, "Blender3GS UI40 FAST: native_frame_done"); }\n#endif'
    s=s[:m.start()]+injection+s[m.end():]
    return s

def patch_draw(s):
    if TAG in s: stop('WM draw already UI40; use --resume')
    if 'BLENDER3GS_UI29_BOOT_TRACE_20260924' not in s or 'BLENDER3GS_UI21_PERF_OVERLAP_PINCH_20260924' not in s:
        stop('draw source not expected UI29/UI21 retained-backing version')
    header='static void wm_method_draw_full(bContext *C, wmWindow *win)\n{'
    s=once(s,header,'#ifdef WITH_IOS\nextern int blender3gs_ui40_python_started(void);\n#endif\n\n' +header,'draw declaration')
    anchor='\t/* draw area regions */\n\tfor (sa = screen->areabase.first; sa; sa = sa->next) {\n\t\tCTX_wm_area_set(C, sa);'
    repl='\t/* draw area regions */\n\tfor (sa = screen->areabase.first; sa; sa = sa->next) {\n#ifdef WITH_IOS\n        /* BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925: first real viewport\n         * before Python; UI editors are blank until native late initialization. */\n        if (!blender3gs_ui40_python_started() && sa->spacetype != SPACE_VIEW3D) {\n            syslog(LOG_WARNING, "Blender3GS UI40 FAST: first_frame_skip_area=%d", sa->spacetype);\n            continue;\n        }\n#endif\n\t\tCTX_wm_area_set(C, sa);'
    return once(s,anchor,repl,'first full area pass')

def verify_input_ipa(path):
    if not path.is_file():stop('UI39 Core IPA not found: '+str(path))
    with zipfile.ZipFile(path) as z:
        if z.testzip():stop('UI39 IPA invalid CRC')
        names=set(z.namelist())
        for p in ('Blender3GS','Info.plist','2.64/scripts/startup/bl_ui/__init__.py'):
            if PFX+p not in names:stop('UI39 IPA lacks '+p)
        info=plistlib.loads(z.read(PFX+'Info.plist'))
        if (str(info.get('CFBundleVersion'))!='39' or
            info.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python' or
            info.get('UIApplicationExitsOnSuspend') is not False):
            stop('IPA not expected UI39 Core identity/version')
        src=z.read(PFX+'2.64/scripts/startup/bl_ui/__init__.py')
        if b'BLENDER3GS_UI39_DIRECT_STARTUP_CORE_20260925' not in src:
            stop('IPA not confirmed UI39 Core script')
        binary=sha(z.read(PFX+'Blender3GS'))
    return binary

def run(name,cmd,log=None,cwd=None):
    print('===',name,'===',flush=True)
    print('COMMAND:', ' '.join(map(str,cmd)),flush=True)
    if log:
        with log.open('w') as f:rc=subprocess.run(list(map(str,cmd)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT).returncode
        if rc:stop(name+' failed: '+str(log)+'\n'+log.read_text(errors='replace')[-12000:])
    else:subprocess.run(list(map(str,cmd)),cwd=cwd,check=True)

def package(root,exe,out,base):
    for x in ('unzip','zip','ldid'):
        if not shutil.which(x):stop('missing '+x)
    with tempfile.TemporaryDirectory(prefix='Blender3GS-UI40-') as td:
        stage=Path(td);run('unpack baseline',['unzip','-q',base,'-d',stage]);app=stage/'Payload'/'Blender3GS.app'
        target=app/'Blender3GS';shutil.copy2(exe,target)
        infofile=app/'Info.plist';info=plistlib.loads(infofile.read_bytes())
        info['CFBundleVersion']='41' # separate from UI39's Full build version=40
        info['CFBundleShortVersionString']='0.40.0'
        info['CFBundleDisplayName']='Blender Py Fast'
        if info.get('UIApplicationExitsOnSuspend') is not False:stop('background Info.plist flag changed')
        infofile.write_bytes(plistlib.dumps(info,fmt=plistlib.FMT_XML))
        shutil.rmtree(app/'_CodeSignature',ignore_errors=True)
        (app/'CodeResources').unlink(missing_ok=True)
        run('sign',['ldid','-S',target])
        partial=out.with_suffix('.partial.ipa')
        if partial.exists():stop('stale partial output: '+str(partial))
        try:
            run('package',['zip','-qry',partial,'Payload'],cwd=stage)
            with zipfile.ZipFile(partial) as z:
                if z.testzip():stop('output CRC failed')
                ver=plistlib.loads(z.read(PFX+'Info.plist'))
                if str(ver.get('CFBundleVersion'))!='41' or ver.get('CFBundleIdentifier')!='io.arutiunio.blender3gs.python':stop('output version/identity mismatch')
                if sha(z.read(PFX+'Blender3GS'))!=sha(target.read_bytes()):stop('packaged executable mismatch')
                with zipfile.ZipFile(base) as zb:
                    for rel in ('2.64/scripts/startup/bl_ui/__init__.py','2.64/scripts/startup/bl_operators/__init__.py','2.64/scripts/modules/bpy/utils.py'):
                        if z.read(PFX+rel)!=zb.read(PFX+rel):stop('Python baseline mutated: '+rel)
            os.replace(partial,out)
        finally:
            if partial.exists():partial.unlink()
    print('SUCCESS: UI40 IPA',out,flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path.home()/'Downloads')
    ap.add_argument('--check-only',action='store_true');ap.add_argument('--resume',action='store_true')
    ap.add_argument('--build-only',action='store_true')
    a=ap.parse_args();root=a.root.expanduser().resolve()
    src=root/'blender-ios6-target';work=root/'blender-ios6-python';build=root/'blender-ios6-build-python'
    exe=root/'Blender3GS-python-armv7';link=root/'blender-link-ios-python-v3.py'
    base=root/BASE;out=root/OUTPUT
    paths={WM:src/WM,INIT:src/INIT,DRAW:src/DRAW}
    backups={r:p.with_name(p.name+'.before-'+TAG) for r,p in paths.items()}
    oldbinary=verify_input_ipa(base)
    output={WM:patch_wm((backups[WM] if a.resume else paths[WM]).read_text()),
            INIT:patch_init((backups[INIT] if a.resume else paths[INIT]).read_text()),
            DRAW:patch_draw((backups[DRAW] if a.resume else paths[DRAW]).read_text())}
    for r,p in paths.items():
        if not p.is_file():stop('missing source '+str(p))
        if not a.resume and backups[r].exists():stop('backup exists '+str(backups[r]))
        if a.resume and p.read_text()!=output[r]:stop('resume source mismatch '+r)
    if out.exists():stop('UI40 IPA already exists; use shell --install-only')
    print('PASS: exact marker and structural anchors; no sources changed yet; old IPA Mach-O SHA256',oldbinary,flush=True)
    print('BEHAVIOR: first C-only Viewport, then Python and UI39 Core startup on main thread',flush=True)
    if a.check_only:return
    for f in (build/'build.ninja',exe,link):
        if not f.is_file():stop('missing build input '+str(f))
    if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):stop('DEVELOPER_DIR / IOS_SDKROOT required')
    work.mkdir(exist_ok=True)
    if not a.resume:
        for r,p in paths.items():
            shutil.copy2(p,backups[r]);p.write_text(output[r]);print('BACKUP/PATCHED:',p,flush=True)
        oldbin=work/('Blender3GS-before-ui40-'+sha(exe.read_bytes())[:12]+'-armv7')
        if not oldbin.exists():shutil.copy2(exe,oldbin)
    run('compile native',['ninja','-C',build,'-j4','bf_windowmanager'],work/'ui-v40-build.log')
    run('relink ARMv7',['python3',link],work/'ui-v40-link.log')
    run('verify ARMv7',['xcrun','lipo','-info',exe],work/'ui-v40-arch.log')
    if 'armv7' not in (work/'ui-v40-arch.log').read_text().lower():stop('not ARMv7')
    package(root,exe,out,base)
    print('WARNING: experimental first draw before Python, may crash; UI39 rollback IPA remains untouched.')

if __name__=='__main__':main()
