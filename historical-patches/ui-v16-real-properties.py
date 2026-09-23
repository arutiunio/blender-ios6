#!/usr/bin/env python3
"""Blender3GS UI16: REPAIR EXISTING Properties area rather than skipping it.

Requires the current successfully built UI15 Python source on the user's Mac.
The bundled UI15 fallback for screens WITHOUT SPACE_BUTS is retained.
For actual stock startup.blend (WITH SPACE_BUTS), hide 3D View T/N shelves,
move the shared area seam to grant Properties ~184 physical pixels, and
replace scroll-clipped icon tabs with seven text-labelled context tabs.

Experimental iOS-only changes; no Touch-v2 files or existing IPAs overwritten.
The --prepare-only flag applies source changes without an ARM build.
"""
from pathlib import Path
import hashlib, os, py_compile, re, shutil, subprocess, sys, zipfile

ROOT=Path(os.environ.get('BLENDER3GS_ROOT',str(Path.home()/'Downloads')))
SRC=ROOT/'blender-ios6-target'
WM=SRC/'source/blender/windowmanager/intern/wm_files.c'
HEADER=SRC/'source/blender/editors/space_buttons/buttons_header.c'
BUILD=ROOT/'blender-ios6-build-python'
WORK=ROOT/'blender-ios6-python'
EXE=ROOT/'Blender3GS-python-armv7'
LINK=ROOT/'blender-link-ios-python-v3.py'
PACK15=WORK/'Blender3GS-package-ui-v15.py'
PACK16=WORK/'Blender3GS-package-ui-v16.py'
IPA=ROOT/'Blender3GS-python-ui-v16-properties.ipa'
TAG='BLENDER3GS_UI16_REAL_PROPERTIES_20260923'
PREP='--prepare-only' in sys.argv


def stop(msg): raise SystemExit('STOP: '+msg)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s,a,b,what):
    n=s.count(a)
    if n!=1: stop('%s: expected one exact source anchor, found %d; nothing modified' % (what,n))
    return s.replace(a,b,1)
def run(name,cmd,log):
    print('\n=== '+name+' ===\nCOMMAND: '+' '.join(map(str,cmd)),flush=True)
    with log.open('w') as h:
        p=subprocess.run(list(map(str,cmd)),stdout=h,stderr=subprocess.STDOUT)
    if p.returncode:
        print(log.read_text(errors='replace')[-20000:]); stop('%s failed (exit %d): %s' % (name,p.returncode,log))
    print('PASS:',log,flush=True)

print('=== 1. VERIFY UI15 EXPERIMENTAL BUILD ===',flush=True)
for p in (WM,HEADER,BUILD/'build.ninja',EXE,LINK,PACK15):
    if not p.is_file() or not p.stat().st_size: stop('missing/empty: '+str(p))
    print('PASS:',p)
if not PREP and not(os.getenv('DEVELOPER_DIR') and os.getenv('IOS_SDKROOT')):
    stop('export DEVELOPER_DIR and IOS_SDKROOT first')
wm=WM.read_text(); header=HEADER.read_text()
if 'BLENDER3GS_MOBILE_LAYOUT_V15_20260923' not in wm or 'existing SPACE_BUTS; preserve layout' not in wm:
    stop('exact UI15 layout helper not found: this patch requires CURRENT UI15 source')
if TAG in wm or TAG in header:stop('UI16 already applied; never patch twice')
if 'BUTTON_HEADER_CTX(BCONTEXT_MODIFIER' not in header or 'BUTTON_HEADER_CTX(BCONTEXT_MATERIAL' not in header:
    stop('unexpected Blender 2.64 Properties header implementation')
if IPA.exists(): stop('UI16 output already exists; refuse to overwrite: '+str(IPA))

print('\n=== 2. FIX EARLY RETURN FOR EXISTING SPACE_BUTS ===',flush=True)
# Exactly the v15 function verified against the complete archived source.
pattern=r'(?s)static void blender3gs_mobile_properties_layout\(bContext \*C\)\n\{.*?\n\}\n#endif'
match=list(re.finditer(pattern,wm))
if len(match)!=1:stop('UI15 function block not uniquely identifiable; found '+str(len(match)))
old=match[0].group(0)
for anchor in ('existing SPACE_BUTS; preserve layout','area_split(screen, view, \'v\', 0.62f, 1)','ED_screen_refresh(wm, win)'):
    if anchor not in old:stop('UI15 helper mismatch: '+anchor)

# This implementation leaves already allocated SpaceButs/regions in place.
# Moving the shared ScrVert seam is crucial: resizing only the Properties
# internal region does NOT increase its ScrArea width.
new=r'''static void blender3gs_mobile_properties_layout(bContext *C)
{
    wmWindowManager *wm = CTX_wm_manager(C);
    wmWindow *win;
    if (!wm || G.background) return;

    for (win = wm->windows.first; win; win = win->next) {
        bScreen *screen = win->screen;
        ScrArea *view, *area, *props = NULL, *left = NULL;
        ScrVert *sv;
        ARegion *tools, *sidebar;
        SpaceButs *sbuts;
        int old_seam, new_seam, right_edge, moved = 0;

        if (!screen || screen->temp || screen->full) continue;
        if (win->sizex < 440 || win->sizex > 560 ||
            win->sizey < 280 || win->sizey > 400) continue;

        /* BLENDER3GS_UI16_REAL_PROPERTIES_20260923: stock startup.blend
         * ALREADY has SPACE_BUTS. The v15 early return bypassed ALL layout
         * changes, hence the visually identical output on the user's 3GS. */
        view = BKE_screen_find_big_area(screen, SPACE_VIEW3D, 0);
        if (!view || view->spacetype != SPACE_VIEW3D) continue;
        for (area = screen->areabase.first; area; area = area->next) {
            syslog(LOG_WARNING, "Blender3GS UI16 AREA: type=%d x=%d..%d y=%d..%d",
                   area->spacetype, area->v1->vec.x, area->v4->vec.x,
                   area->v1->vec.y, area->v2->vec.y);
            if (area->spacetype == SPACE_BUTS &&
                (!props || area->v4->vec.x > props->v4->vec.x))
                props = area;
        }
        CTX_wm_window_set(C, win);
        CTX_wm_region_set(C, NULL);
        tools = BKE_area_find_region_type(view, RGN_TYPE_TOOLS);
        sidebar = BKE_area_find_region_type(view, RGN_TYPE_UI);
        if (tools) tools->flag |= RGN_FLAG_HIDDEN;
        if (sidebar) sidebar->flag |= RGN_FLAG_HIDDEN;
        syslog(LOG_WARNING, "Blender3GS UI16 VIEW: x=%d..%d T=%d N=%d",
               view->v1->vec.x, view->v4->vec.x, !!tools, !!sidebar);

        if (!props) {
            /* Preserve v15's supported fallback for a startup with no
             * Properties area. 'v' makes new LEFT View3D, old RIGHT Buttons. */
            if (view->v4->vec.x - view->v1->vec.x >= 410) {
                CTX_wm_area_set(C, view);
                left = area_split(screen, view, 'v', 0.62f, 1);
                if (left) {
                    CTX_wm_area_set(C, view);
                    ED_area_newspace(C, view, SPACE_BUTS);
                    props = view;
                    view = left;
                    syslog(LOG_WARNING, "Blender3GS UI16: created native SPACE_BUTS");
                }
            }
        }
        if (props) {
            old_seam = props->v1->vec.x;
            right_edge = props->v4->vec.x;
            new_seam = right_edge - 184;
            if (new_seam < view->v1->vec.x + 180)
                new_seam = view->v1->vec.x + 180;
            /* Only move the common right-column seam. Keep the screen's
             * external frame and all horizontal divider vertices intact. */
            if (!left && right_edge >= win->sizex - 18 &&
                old_seam > new_seam + 10 && old_seam > 0) {
                for (sv = screen->vertbase.first; sv; sv = sv->next) {
                    if (sv->vec.x == old_seam) {
                        sv->vec.x = new_seam;
                        moved++;
                    }
                }
            }
            sbuts = (SpaceButs *)props->spacedata.first;
            if (sbuts && props->spacetype == SPACE_BUTS) {
                sbuts->align = BUT_VERTICAL;
                sbuts->mainb = BCONTEXT_MODIFIER;
                sbuts->mainbuser = BCONTEXT_MODIFIER;
            }
            syslog(LOG_WARNING,
                   "Blender3GS UI16 RESIZE: old=%d target=%d moved=%d Properties=%d..%d h=%d",
                   old_seam, new_seam, moved,
                   props->v1->vec.x, props->v4->vec.x,
                   props->v2->vec.y - props->v1->vec.y);
        }
        CTX_wm_region_set(C, NULL);
        CTX_wm_area_set(C, NULL);
        screen->do_refresh = TRUE;
        ED_screen_refresh(wm, win);
        for (area = screen->areabase.first; area; area = area->next) {
            ED_area_tag_redraw(area);
            ED_area_tag_refresh(area);
        }
        syslog(LOG_WARNING, "Blender3GS UI16 READY: native Properties=%d; screen=%dx%d",
               props != NULL, win->sizex, win->sizey);
    }
    /* Keep the window context, as v15 does: WM_homefile_read continues
     * executing Python initialization and LOAD_POST callbacks after us. */
    CTX_wm_region_set(C, NULL);
    CTX_wm_area_set(C, NULL);
}
#endif'''
wm=wm[:match[0].start()]+new+wm[match[0].end():]
if TAG not in wm:stop('internal helper patch not applied')

print('\n=== 3. COMPACT, TEXT-LABELLED NATIVE PROPERTIES TABS ===',flush=True)
# Retains native ROW context-switching, callbacks, and Python panel content.
# At 480px width, the 7 essential tabs fit into a ~184px Properties area.
first='\tBUTTON_HEADER_CTX(BCONTEXT_RENDER, ICON_SCENE, N_("Render"));'
last='\tBUTTON_HEADER_CTX(BCONTEXT_PHYSICS, ICON_PHYSICS, N_("Physics"));'
if header.count(first)!=1 or header.count(last)!=1:stop('unexpected original Properties tabs')
a=header.index(first);b=header.index(last)+len(last)
old_tabs=header[a:b]
new_tabs=r'''#ifdef WITH_IOS
    /* BLENDER3GS_UI16_REAL_PROPERTIES_20260923: original 13 icon tabs
     * overflow a 184px column; show the essential native contexts as text. */
#define BLENDER3GS_MOBILE_CTX(_ctx, _label, _tip) \
    if (sbuts->pathflag & (1 << _ctx)) { \
        but = uiDefButS(block, ROW, B_CONTEXT_SWITCH, _label, xco += BUT_UNIT_X, yco, BUT_UNIT_X, UI_UNIT_Y, &(sbuts->mainb), 0.0, (float)_ctx, 0, 0, TIP_(_tip)); \
        uiButClearFlag(but, UI_BUT_UNDO); \
    } (void)0
    BLENDER3GS_MOBILE_CTX(BCONTEXT_RENDER,   "R",  N_("Render settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_SCENE,    "S",  N_("Scene settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_WORLD,    "W",  N_("World settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_OBJECT,   "O",  N_("Object settings"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_MODIFIER, "M",  N_("Object modifiers"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_DATA,     "D",  N_("Object data"));
    BLENDER3GS_MOBILE_CTX(BCONTEXT_MATERIAL, "Mt", N_("Materials"));
#undef BLENDER3GS_MOBILE_CTX
#else
'''+old_tabs+r'''
#endif'''
header=header[:a]+new_tabs+header[b:]
if 'BLENDER3GS_MOBILE_CTX(BCONTEXT_MODIFIER' not in header:stop('missing Modifiers tab')
if 'BLENDER3GS_MOBILE_CTX(BCONTEXT_RENDER' not in header:stop('missing Render tab')
if 'BLENDER3GS_MOBILE_CTX(BCONTEXT_MATERIAL' not in header:stop('missing Material tab')

pkg=PACK15.read_text()
pkg=once(pkg,'Blender3GS-python-ui-v15-properties.ipa',IPA.name,'IPA output name')
for name,val in [('CFBundleVersion','16'),('CFBundleShortVersionString','0.16.0')]:
    p=r"(info\['"+name+r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(p,pkg))!=1:stop('unexpected version field in packager: '+name)
    pkg=re.sub(p,lambda m:m.group(1)+repr(val),pkg,count=1)
for f,old_src,new_src in [(WM,WM.read_text(),wm),(HEADER,HEADER.read_text(),header)]:
    if old_src==new_src:stop('unchanged source: '+str(f))
    if f.with_name(f.name+'.before-ios6-ui16').exists():stop('backup already exists: '+str(f))
if PACK16.exists():stop('new packager already exists; protect previous run')
print('PASS: all transformations & package output checked in memory')

print('\n=== 4. BACKUP AND APPLY CURRENT SOURCE ===',flush=True)
for f,content in [(WM,wm),(HEADER,header)]:
    backup=f.with_name(f.name+'.before-ios6-ui16')
    shutil.copy2(f,backup)
    f.write_text(content)
    print('BACKUP:',backup,'\nPATCHED:',f,flush=True)
if PREP:
    print('SUCCESS: UI16 PREPARE-ONLY (no build or IPA)')
    raise SystemExit(0)
WORK.mkdir(parents=True,exist_ok=True)
old_hash=sha(EXE)
prev=WORK/'Blender3GS-python-before-ui-v16-armv7'
if not prev.exists():shutil.copy2(EXE,prev)

print('\n=== 5. RESOLVE EXACT NINJA TARGETS ===',flush=True)
res=subprocess.run(['ninja','-C',str(BUILD),'-t','targets','all'],capture_output=True,text=True)
if res.returncode:stop('ninja target listing failed: '+res.stderr[-3000:])
targets=res.stdout
selected=[]
for preferred,archive in [('bf_windowmanager','libbf_windowmanager.a'),('bf_editor_space_buttons','libbf_editor_space_buttons.a')]:
    candidates=[line.split(':',1)[0] for line in targets.splitlines() if line.split(':',1)[0].endswith('/'+archive) or line.split(':',1)[0]==archive]
    if candidates:selected.append(candidates[0])
    elif re.search(r'^'+re.escape(preferred)+r':',targets,re.M):selected.append(preferred)
    else:stop('required Ninja target unavailable: '+preferred+'; inspect build.ninja')
print('TARGETS:',selected)
run('6. BUILD WINDOW MANAGER + PROPERTIES',['ninja','-C',BUILD,'-j4',*selected],WORK/'ui-v16-build.log')
run('7. RELINK WITH ALL EXISTING PYTHON/RNA/ATEXIT FIXES',['python3',LINK],WORK/'ui-v16-link.log')
if sha(EXE)==old_hash:stop('linked executable unchanged; refuse to package previous version')
run('8. VERIFY ARMv7',['xcrun','lipo','-info',EXE],WORK/'ui-v16-arch.log')
if 'armv7' not in (WORK/'ui-v16-arch.log').read_text():stop('not an ARMv7 binary')
PACK16.write_text(pkg)
py_compile.compile(str(PACK16),doraise=True)
run('9. PACKAGE UI16 IPA',['python3',PACK16],WORK/'ui-v16-package.log')
if not IPA.is_file() or IPA.stat().st_size<1000000:stop('new IPA missing or too small')
with zipfile.ZipFile(IPA) as z:
    if z.testzip():stop('IPA archive fails CRC check')
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():stop('IPA missing executable')
print('\nSUCCESS: UI16 DEVICE TEST CANDIDATE:',IPA,flush=True)
print('LOG: Blender3GS UI16 AREA / VIEW / RESIZE / READY',flush=True)
print('Touch v2 and previous packaged UI versions unchanged.',flush=True)