#!/usr/bin/env python3
"""Blender 3GS: reversible popup compositing candidate + usable trackpad controls.

Runs on the user's Mac. Requires their existing complete Blender 2.64 source,
armv7 toolchain, Python+RNA+atexit linker and cleanui packager. The uploaded IPA
alone cannot be recompiled. Preserves original Touch v2 and all older IPAs.

This is a device-test candidate, not a claim that every graphics issue is solved.
"""
from pathlib import Path
import ast
import hashlib
import os
import py_compile
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path.home() / 'Downloads'
SRC = ROOT / 'blender-ios6-target'
BUILD = ROOT / 'blender-ios6-build-python'
WORK = ROOT / 'blender-ios6-python'
GHOST = SRC / 'intern/ghost/intern/GHOST_WindowIOS.mm'
REGION = SRC / 'source/blender/editors/interface/interface_regions.c'
WIDGETS = SRC / 'source/blender/editors/interface/interface_widgets.c'
WIDGETS_ORIG = WIDGETS.with_name('interface_widgets.c.before-ios6-popup-width-test')
WIDGETS_SCRIPT = ROOT / 'Blender3GS-popup-width-test.py'
BINARY = ROOT / 'Blender3GS-python-armv7'
LINKER = ROOT / 'blender-link-ios-python-v3.py'
PACKAGER = WORK / 'Blender3GS-package-cleanui.py'
NEW_PACKAGER = WORK / 'Blender3GS-package-popup-trackpad.py'
OUTPUT_IPA = ROOT / 'Blender3GS-python-popup-trackpad-test.ipa'
TAG = 'BLENDER3GS_POPUP_TRACKPAD_20260923'
PREPARE_ONLY = '--prepare-only' in sys.argv


def stop(s):
    raise SystemExit('STOP: ' + s)


def show(s):
    print('\n=== ' + s + ' ===', flush=True)


def run(label, args, log):
    show(label)
    print('COMMAND:', ' '.join(map(str, args)), flush=True)
    with log.open('w') as out:
        status = subprocess.run(list(map(str, args)), stdout=out, stderr=subprocess.STDOUT)
    if status.returncode:
        print(log.read_text(errors='replace')[-16000:], flush=True)
        stop('exit %d; see %s' % (status.returncode, log))
    print('PASS:', log, flush=True)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_vars(path, names):
    tree = ast.parse(path.read_text())
    out = {}
    for item in tree.body:
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            name = item.targets[0].id
            if name in names:
                try:
                    out[name] = ast.literal_eval(item.value)
                except (ValueError, TypeError, SyntaxError):
                    pass
    if set(out) != set(names):
        stop('previous diagnostic script has unexpected contents: %s' % path)
    return out


def restore_widget_test():
    current = WIDGETS.read_text()
    if 'Blender3GS iOS6 POPUP TEXT WIDTH A/B TEST' not in current:
        print('PASS: width diagnostic already absent')
        return None
    if not WIDGETS_ORIG.is_file() or not WIDGETS_SCRIPT.is_file():
        stop('width diagnostic backup/script missing; refusing unsafe undo')
    t = literal_vars(WIDGETS_SCRIPT, ['needle', 'inject', 'header', 'include_insert'])
    orig = WIDGETS_ORIG.read_text()
    start = orig.find('static void ui_text_clip_left(')
    end = orig.find('\n/**\n * Cut off the text, taking into account the cursor', start)
    if min(start, end) < 0:
        stop('unknown original widget function')
    part = orig[start:end]
    if part.count(t['needle']) != 1 or orig.count(t['header']) != 1:
        stop('widget backup does not match previous diagnostic script')
    expected_part = part.replace(t['needle'], t['inject'], 1)
    expected = orig.replace(t['header'], t['header'] + t['include_insert'], 1)
    st = expected.find('static void ui_text_clip_left(')
    en = expected.find('\n/**\n * Cut off the text, taking into account the cursor', st)
    expected = expected[:st] + expected_part + expected[en:]
    if expected != current:
        stop('widget file changed since width test; manual diff required')
    print('VERIFIED: width-only diagnostic is exactly reversible')
    return orig


def replace_exact(src, old, new, label):
    if src.count(old) != 1:
        stop('%s: expected one matching block, got %s' % (label, src.count(old)))
    return src.replace(old, new, 1)


show('1. PREFLIGHT; experimental project only')
for p in [GHOST, REGION, WIDGETS, BUILD/'build.ninja', BINARY, LINKER, PACKAGER]:
    if not p.is_file() or not p.stat().st_size:
        stop('missing: %s' % p)
    print('PASS:', p)
if not PREPARE_ONLY and not (os.environ.get('DEVELOPER_DIR') and os.environ.get('IOS_SDKROOT')):
    stop('export DEVELOPER_DIR and IOS_SDKROOT')
for p in [REGION, GHOST]:
    if TAG in p.read_text():
        stop('already patched: %s. Do not run a second time.' % p)

widgets_restored = restore_widget_test()

show('2. POPUP: isolate draw state from 3D viewport')
reg_text = REGION.read_text()
old_region = '''static void ui_block_region_draw(const bContext *C, ARegion *ar)
{
\tuiBlock *block;

\tfor (block = ar->uiblocks.first; block; block = block->next)
\t\tuiDrawBlock(C, block);
}'''
new_region = '''static void ui_block_region_draw(const bContext *C, ARegion *ar)
{
\tuiBlock *block;
#ifdef WITH_IOS
\t/* BLENDER3GS_POPUP_TRACKPAD_20260923: menu pixels must not inherit
\t * depth/cull/stencil tests from the preceding 3D View. This is a
\t * reversible compositing candidate, not a font/BLF modification. */
\tconst GLboolean prev_depth = glIsEnabled(GL_DEPTH_TEST);
\tconst GLboolean prev_cull = glIsEnabled(GL_CULL_FACE);
\tconst GLboolean prev_stencil = glIsEnabled(GL_STENCIL_TEST);
\tstatic int item_log_count = 0;
\tif (item_log_count < 40) {
\t\tGLint vp[4] = {0, 0, 0, 0};
\t\tglGetIntegerv(GL_VIEWPORT, vp);
\t\tsyslog(LOG_WARNING, "Blender3GS POPUP STATE: viewport=%d,%d,%d,%d depth=%d cull=%d stencil=%d",
\t\t       vp[0], vp[1], vp[2], vp[3], (int)prev_depth, (int)prev_cull, (int)prev_stencil);
\t}
\tglFlush();
\tglDisable(GL_DEPTH_TEST);
\tglDisable(GL_CULL_FACE);
\tglDisable(GL_STENCIL_TEST);
#endif
\tfor (block = ar->uiblocks.first; block; block = block->next) {
#ifdef WITH_IOS
\t\tif (item_log_count < 40) {
\t\t\tuiBut *but;
\t\t\tfor (but = block->buttons.first; but && item_log_count < 40; but = but->next) {
\t\t\t\tsyslog(LOG_WARNING, "Blender3GS POPUP ITEM: type=%d emboss=%d label='%.64s' rect=(%.0f,%.0f)-(%.0f,%.0f)",
\t\t\t\t       (int)but->type, (int)but->dt, but->drawstr,
\t\t\t\t       (double)but->rect.xmin, (double)but->rect.ymin,
\t\t\t\t       (double)but->rect.xmax, (double)but->rect.ymax);
\t\t\t\titem_log_count++;
\t\t\t}
\t\t}
#endif
\t\tuiDrawBlock(C, block);
\t}
#ifdef WITH_IOS
\tglFlush();
\tif (prev_depth) glEnable(GL_DEPTH_TEST);
\tif (prev_cull) glEnable(GL_CULL_FACE);
\tif (prev_stencil) glEnable(GL_STENCIL_TEST);
#endif
}'''
reg_new = replace_exact(reg_text, old_region, new_region, 'popup draw function')
reg_new = replace_exact(reg_new, '#include <assert.h>\n', '#include <assert.h>\n#ifdef WITH_IOS\n#  include <syslog.h>\n#endif\n', 'popup syslog header')
print('PASS: changed only temporary popup draw wrapper')

show('3. TRACKPAD: replace touch interpreter, keep GL and native Blender UI')
ghost_text = GHOST.read_text()
if 'BLENDER_IOS6_GESTURES_V2' not in ghost_text:
    stop('not the expected iOS6 Touch-v2-based GHOST bridge')
if 'Blender3GS iOS6: native UI; no redundant overlay buttons' not in ghost_text:
    stop('Clean UI patch missing; refuse to recreate overlapping buttons')
if '[self installControls];' in ghost_text[ghost_text.find('- (void)bindGhostSystem:'):ghost_text.find('- (UIButton *)newControl:')]:
    stop('overlay buttons are still active; Clean UI build expected')

old_ivar = '''    UIButton *m_viewButton;        /* retained by the view hierarchy */'''
new_ivar = '''    UIButton *m_viewButton;        /* retained by the view hierarchy */
    /* BLENDER3GS_POPUP_TRACKPAD_20260923: iPhone 3GS virtual trackpad. */
    CGPoint m_pointer;
    CGPoint m_previousPrimary;
    CGPoint m_previousSecondary;
    CGFloat m_previousPinchDistance;
    BOOL m_pointerReady;
    BOOL m_singleMoved;
    BOOL m_dragDown;
    BOOL m_middleDown;
    BOOL m_pinching;
    int m_zoomAccumulator;
    UIView *m_pointerDot;'''
ghost_new = replace_exact(ghost_text, old_ivar, new_ivar, 'GHOST view ivars')
if '#include <math.h>' not in ghost_new:
    ghost_new = replace_exact(ghost_new, '#include <stdio.h>\n', '#include <stdio.h>\n#include <math.h>\n', 'math declarations')
start = ghost_new.find('- (void)beginLongPress\n{')
end = ghost_new.find('\n- (void)dealloc\n{', start)
if start < 0 or end < 0 or end <= start:
    stop('unexpected touch method boundaries')
old_touch_section = ghost_new[start:end]
for mandatory in ['- (void)touchesBegan:', '- (void)touchesMoved:', '- (void)finishTouches:',
                  '- (void)touchesEnded:', '- (void)touchesCancelled:',
                  '- (void)releaseTouch:', 'IOS6GestureTwoFinger', 'GHOST_kButtonMaskMiddle']:
    if mandatory not in old_touch_section:
        stop('unexpected touch interpreter: missing ' + mandatory)

new_touch_section = '''/* BLENDER3GS_POPUP_TRACKPAD_20260923
 * The finger acts as a relative pointer, like a laptop trackpad.
 * The on-screen dot is visual only; Blender gets standard GHOST events.
 * A tap always produces a left click so an overlapping popup remains
 * clickable even when it covers the 3D View. Blender 2.64 defaults to
 * right-click selection, available via two-finger tap on this trackpad.
 */
- (void)ensurePointer:(CGPoint)firstTouch
{
    if (!m_pointerReady) {
        m_pointer = firstTouch;
        m_pointerReady = YES;
    }
    if (!m_pointerDot) {
        UIView *dot = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 7, 7)];
        dot.userInteractionEnabled = NO;
        dot.backgroundColor = [UIColor whiteColor];
        dot.layer.cornerRadius = 3.5f;
        dot.layer.borderWidth = 1.0f;
        dot.layer.borderColor = [UIColor blackColor].CGColor;
        [self addSubview:dot];
        m_pointerDot = dot;
        [dot release];
    }
    [self pointPointerBy:CGPointZero];
}

- (void)pointPointerBy:(CGPoint)delta
{
    const CGRect b = self.bounds;
    m_pointer.x += delta.x * 1.10f;
    m_pointer.y += delta.y * 1.10f;
    m_pointer.x = MAX(2.0f, MIN(m_pointer.x, b.size.width - 3.0f));
    m_pointer.y = MAX(2.0f, MIN(m_pointer.y, b.size.height - 3.0f));
    if (m_pointerDot)
        m_pointerDot.center = m_pointer;
    [self cursorAt:m_pointer];
}

- (void)tapAtPointer:(GHOST_TButtonMask)button
{
    [self cursorAt:m_pointer];
    [self button:button down:YES];
    [self button:button down:NO];
}

- (void)beginLongPress
{
    if (m_mode != IOS6GesturePending || !m_primaryTouch || m_secondaryTouch)
        return;
    /* Holding starts a normal LMB drag, not Blender's destructive G operator. */
    [self cursorAt:m_pointer];
    [self button:GHOST_kButtonMaskLeft down:YES];
    m_dragDown = YES;
    m_mode = IOS6GestureUI;
}

- (void)cancelLongPress
{
    [NSObject cancelPreviousPerformRequestsWithTarget:self
                                             selector:@selector(beginLongPress)
                                               object:nil];
}

- (void)releaseTouch:(UITouch **)slot
{
    if (*slot) { [*slot release]; *slot = nil; }
}

- (void)sendZoomStep:(BOOL)zoomIn
{
    if (!m_ghostSystem || !m_ghostWindow) return;
    GHOST_TKey key = zoomIn ? GHOST_kKeyNumpadPlus : GHOST_kKeyNumpadMinus;
    m_ghostSystem->ios6Key(m_ghostWindow, key, true);
    m_ghostSystem->ios6Key(m_ghostWindow, key, false);
}

- (void)touchesBegan:(NSSet *)touches withEvent:(UIEvent *)event
{
    if (!m_ghostSystem || !m_ghostWindow) return;
    for (UITouch *touch in touches) {
        if (!m_primaryTouch) {
            m_primaryTouch = [touch retain];
            const CGPoint p = [touch locationInView:self];
            [self ensurePointer:p];
            m_previousPrimary = p;
            m_origin = p;
            m_started = [NSDate timeIntervalSinceReferenceDate];
            m_singleMoved = NO;
            m_mode = IOS6GesturePending;
            [self performSelector:@selector(beginLongPress) withObject:nil afterDelay:0.38];
        }
        else if (!m_secondaryTouch && touch != m_primaryTouch) {
            m_secondaryTouch = [touch retain];
            m_previousSecondary = [touch locationInView:self];
            [self cancelLongPress];
            if (m_dragDown) {
                [self button:GHOST_kButtonMaskLeft down:NO];
                m_dragDown = NO;
            }
            m_twoFingerMoved = NO;
            m_middleDown = NO;
            m_pinching = NO;
            m_zoomAccumulator = 0;
            m_previousPinchDistance = hypotf(m_previousPrimary.x - m_previousSecondary.x,
                                            m_previousPrimary.y - m_previousSecondary.y);
            m_started = [NSDate timeIntervalSinceReferenceDate];
            m_mode = IOS6GestureTwoFinger;
        }
    }
}

- (void)touchesMoved:(NSSet *)touches withEvent:(UIEvent *)event
{
    if (!m_primaryTouch || !m_ghostSystem || !m_ghostWindow) return;
    const CGPoint p = [m_primaryTouch locationInView:self];
    if (m_mode == IOS6GestureTwoFinger && m_secondaryTouch) {
        const CGPoint q = [m_secondaryTouch locationInView:self];
        const CGPoint delta = CGPointMake(((p.x - m_previousPrimary.x) +
                                            (q.x - m_previousSecondary.x)) * .5f,
                                           ((p.y - m_previousPrimary.y) +
                                            (q.y - m_previousSecondary.y)) * .5f);
        const CGFloat separation = hypotf(p.x - q.x, p.y - q.y);
        const CGFloat pinchDelta = separation - m_previousPinchDistance;
        if (fabsf(pinchDelta) > 5.0f && !m_middleDown)
            m_pinching = YES;
        if (m_pinching) {
            m_zoomAccumulator += (int)pinchDelta;
            if (m_zoomAccumulator > 14) {
                [self sendZoomStep:YES];
                m_zoomAccumulator = 0;
            }
            else if (m_zoomAccumulator < -14) {
                [self sendZoomStep:NO];
                m_zoomAccumulator = 0;
            }
            if (fabsf(pinchDelta) > 2.0f) m_twoFingerMoved = YES;
        }
        else if (fabsf(delta.x) + fabsf(delta.y) > 2.5f) {
            if (!m_middleDown) {
                [self cursorAt:m_pointer];
                [self button:GHOST_kButtonMaskMiddle down:YES];
                m_middleDown = YES;
            }
            [self pointPointerBy:delta];
            m_twoFingerMoved = YES;
        }
        m_previousPrimary = p;
        m_previousSecondary = q;
        m_previousPinchDistance = separation;
        return;
    }
    const CGPoint delta = CGPointMake(p.x - m_previousPrimary.x,
                                      p.y - m_previousPrimary.y);
    m_previousPrimary = p;
    if (fabsf(p.x - m_origin.x) + fabsf(p.y - m_origin.y) > 5.0f) {
        m_singleMoved = YES;
        [self cancelLongPress];
    }
    [self pointPointerBy:delta];
}

- (void)finishTouches:(NSSet *)touches cancelled:(BOOL)cancelled
{
    if (!m_primaryTouch && !m_secondaryTouch) return;
    if (m_mode == IOS6GestureTwoFinger) {
        const NSTimeInterval t = [NSDate timeIntervalSinceReferenceDate] - m_started;
        if (m_middleDown) [self button:GHOST_kButtonMaskMiddle down:NO];
        if (!cancelled && !m_twoFingerMoved && t < 0.55)
            [self tapAtPointer:GHOST_kButtonMaskRight];
        /* End both fingers together; next single touch starts a fresh gesture. */
        [self releaseTouch:&m_primaryTouch];
        [self releaseTouch:&m_secondaryTouch];
        m_middleDown = NO;
        m_pinching = NO;
        m_mode = IOS6GestureIdle;
        return;
    }
    if (![touches containsObject:m_primaryTouch]) return;
    [self cancelLongPress];
    if (m_dragDown) {
        [self button:GHOST_kButtonMaskLeft down:NO];
        m_dragDown = NO;
    }
    else if (!cancelled && !m_singleMoved) {
        /* Do not infer "viewport" using screen percentages: Blender popup
         * menus are floating regions and can cover any part of the viewport.
         * Normal click is LMB everywhere, as with a Mac trackpad. */
        [self tapAtPointer:GHOST_kButtonMaskLeft];
    }
    [self releaseTouch:&m_primaryTouch];
    m_mode = IOS6GestureIdle;
}

- (void)touchesEnded:(NSSet *)touches withEvent:(UIEvent *)event
{
    [self finishTouches:touches cancelled:NO];
}

- (void)touchesCancelled:(NSSet *)touches withEvent:(UIEvent *)event
{
    [self finishTouches:touches cancelled:YES];
}
'''
ghost_new = ghost_new[:start] + new_touch_section + ghost_new[end:]
if ghost_new.count(TAG) < 2 or '- (void)beginLongPress\n{' not in ghost_new:
    stop('unexpected touch patch output')
print('PASS: virtual cursor, 1-finger relative motion, hold-drag, 2-finger MMB/right click, pinch +/-')

show('4. COMMIT MODIFICATIONS WITH UNIQUE BACKUPS')
backups = [(REGION, REGION.with_name('interface_regions.c.before-' + TAG)),
           (GHOST, GHOST.with_name('GHOST_WindowIOS.mm.before-' + TAG))]
for src, bak in backups:
    if bak.exists():
        stop('backup exists; refuse to overwrite: ' + str(bak))
for src, bak in backups:
    shutil.copy2(src, bak)
REGION.write_text(reg_new)
GHOST.write_text(ghost_new)
if widgets_restored is not None:
    WIDGETS.write_text(widgets_restored)
    print('RESTORED: failed popup width diagnostic, verified byte-for-byte')
for src, bak in backups:
    print('PATCHED:', src)
    print('BACKUP:', bak)
if PREPARE_ONLY:
    print('PASS: local source patch; no build or IPA attempted')
    raise SystemExit(0)

old_hash = sha256(BINARY)
if not (WORK / ('Blender3GS-python-before-' + TAG + '-armv7')).exists():
    shutil.copy2(BINARY, WORK / ('Blender3GS-python-before-' + TAG + '-armv7'))

run('5. BUILD BOTH LIBRARIES',
    ['ninja', '-C', BUILD, '-j4', 'bf_editor_interface', 'bf_intern_ghost'], WORK / 'popup-trackpad-build.log')
run('6. RELINK PYTHON + RNA + ATEXIT', ['python3', LINKER], WORK / 'popup-trackpad-link.log')
if sha256(BINARY) == old_hash:
    stop('executable did not change; refusing stale IPA')
run('7. VERIFY ARCH', ['xcrun', 'lipo', '-info', BINARY], WORK / 'popup-trackpad-arch.log')
arch_log = (WORK / 'popup-trackpad-arch.log').read_text()
if 'armv7' not in arch_log:
    stop('not armv7')
nm = subprocess.run(['xcrun', 'nm', '-g', str(BINARY)], capture_output=True, text=True)
if nm.returncode or not re.search(r'\b[Tt]\s+_PyInit_atexit\b', nm.stdout):
    stop('missing PyInit_atexit')

show('8. CREATE A NEW IPA; original Touch v2 untouched')
pkg = PACKAGER.read_text()
old_name = 'Blender3GS-python-cleanui-test.ipa'
if pkg.count(old_name) != 1:
    stop('cleanui package script changed; inspect before creating IPA')
pkg = pkg.replace(old_name, OUTPUT_IPA.name, 1)
for k, v in [('CFBundleVersion', '10'), ('CFBundleShortVersionString', '0.10.0')]:
    pat = r"(info\['" + k + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pat, pkg)) != 1:
        stop('unexpected packager version field: ' + k)
    pkg = re.sub(pat, lambda m: m.group(1) + repr(v), pkg, count=1)
NEW_PACKAGER.write_text(pkg)
py_compile.compile(str(NEW_PACKAGER), doraise=True)
run('9. PACKAGE', ['python3', NEW_PACKAGER], WORK / 'popup-trackpad-package.log')
if not OUTPUT_IPA.is_file() or not OUTPUT_IPA.stat().st_size:
    stop('IPA not produced')
with zipfile.ZipFile(OUTPUT_IPA) as z:
    if z.testzip():
        stop('IPA zip test failed')
    if not {'Payload/Blender3GS.app/Blender3GS', 'Payload/Blender3GS.app/Info.plist'} <= set(z.namelist()):
        stop('IPA missing binary or plist')
print('\nSUCCESS: TEST CANDIDATE:', OUTPUT_IPA)
print('NOTE: popup rendering is NOT confirmed until tested on the real iPhone 3GS.')
print('The working Touch-v2 IPA and every earlier experimental IPA are unchanged.')