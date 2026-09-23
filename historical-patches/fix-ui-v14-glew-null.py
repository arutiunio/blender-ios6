#!/usr/bin/env python3
"""Blender 3GS UI14: repair UI13 null GLEW glActiveTexture call.

Keep UI13 source/tree/optimizations intact, patch ONLY the two newly inserted
uninitialized GLEW function-pointer calls. Fail closed on an unfamiliar tree.
The user's known-good Touch v2 is never touched.
"""
from pathlib import Path
import os
import re
import sys
import shutil
import hashlib
import subprocess
import zipfile
import py_compile

ROOT = Path(os.environ.get('BLENDER3GS_ROOT', str(Path.home() / 'Downloads')))
SRC = ROOT / 'blender-ios6-target'
BLF = SRC / 'source/blender/blenfont/intern/blf.c'
ICONS = SRC / 'source/blender/editors/interface/interface_icons.c'
DRAW = SRC / 'source/blender/windowmanager/intern/wm_draw.c'
GHOST = SRC / 'intern/ghost/intern/GHOST_WindowIOS.mm'
BUILD = ROOT / 'blender-ios6-build-python'
WORK = ROOT / 'blender-ios6-python'
EXEC = ROOT / 'Blender3GS-python-armv7'
LINK = ROOT / 'blender-link-ios-python-v3.py'
PACK13 = WORK / 'Blender3GS-package-ui-v13.py'
PACK14 = WORK / 'Blender3GS-package-ui-v14.py'
IPA = ROOT / 'Blender3GS-python-ui-v14-test.ipa'
BACKUP_TAG = 'before-ios6-ui14-glew-null'
TAG = 'BLENDER3GS_UI_V14_GLEW_NULL_20260923'
PREP = '--prepare-only' in sys.argv


def stop(message):
    raise SystemExit('STOP: ' + message)


def unique_replace(source, before, after, label):
    n = source.count(before)
    if n != 1:
        stop(f'{label}: expected exactly one anchor; found {n}; no source files modified')
    return source.replace(before, after, 1)


def call(title, args, log):
    print('\n=== ' + title + ' ===', flush=True)
    print('COMMAND:', ' '.join(str(x) for x in args), flush=True)
    with log.open('w') as f:
        result = subprocess.run([str(x) for x in args], stdout=f, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        print(log.read_text(errors='replace')[-20000:])
        stop(f'{title}: exit {result.returncode}; inspect {log}')
    print('PASS:', log, flush=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


print('=== 1. PREFLIGHT: EXACT EXPERIMENTAL UI13 ===', flush=True)
for path in (BLF, ICONS, DRAW, GHOST, BUILD / 'build.ninja', EXEC, LINK, PACK13):
    if not path.is_file() or not path.stat().st_size:
        stop('missing or empty: ' + str(path))
    print('PASS:', path)
if not PREP and not (os.environ.get('DEVELOPER_DIR') and os.environ.get('IOS_SDKROOT')):
    stop('set DEVELOPER_DIR and IOS_SDKROOT before running')

orig_blf = BLF.read_text()
orig_icons = ICONS.read_text()
if TAG in orig_blf or TAG in orig_icons:
    stop('UI14 already applied; do not run twice')
if 'BLENDER3GS_UI_V13_20260923' not in orig_blf or 'BLENDER3GS_UI_V13_20260923' not in orig_icons:
    stop('UI13 is not present in font/icon source; refusing to patch an unknown state')
if 'BLENDER3GS_UI_V13_20260923' not in DRAW.read_text() or 'BLENDER3GS_UI_V13_20260923' not in GHOST.read_text():
    stop('UI13 compositor/retained-backing sources missing; refusing mixed-build state')

print('\n=== 2. PREPARE TWO PRECISE CORRECTIONS IN MEMORY ===', flush=True)
# The crash PC is 0, r0 is 0x84C0 (GL_TEXTURE0), and UI13 inserted two
# calls to glActiveTexture(GL_TEXTURE0). In this GLES2/GL4ES build, gl.h's
# GLEW glActiveTexture resolves via an uninitialized __glewActiveTexture
# function pointer. UI12 operated without these calls.
old_blf = '''#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V13_20260923: Blender's GLES2 shader samples unit 0;
\t * viewport code may have left another texture unit active. Set the
\t * same unit before any font atlas binding/upload. */
\tglActiveTexture(GL_TEXTURE0);
#endif
\t/* always bind the texture for the first glyph */'''
new_blf = '''#ifdef WITH_IOS
\t/* BLENDER3GS_UI_V14_GLEW_NULL_20260923: UI13 called the GLEW
\t * glActiveTexture pointer before it was initialized. It branched to
\t * address zero with GL_TEXTURE0 (0x84c0) in r0. Do not call the GLEW
\t * dispatch here; the previously working UI12 bind path remains. */
#endif
\t/* always bind the texture for the first glyph */'''
new_blf_text = unique_replace(orig_blf, old_blf, new_blf, 'BLF null dispatch')

old_icon = '''\t\t\t\t\t/* BLENDER3GS_UI_V13_20260923: sampler0 is the GPU
\t\t\t\t\t * shader's atlas unit; don't inherit viewport active unit. */
\t\t\t\t\tglActiveTexture(GL_TEXTURE0);
\t\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\t\tglPixelStorei(GL_UNPACK_ALIGNMENT, 4);'''
new_icon = '''\t\t\t\t\t/* BLENDER3GS_UI_V14_GLEW_NULL_20260923: no unsafe
\t\t\t\t\t * GLEW glActiveTexture function-pointer call here. The
\t\t\t\t\t * GL4ES texture binding below worked in UI12. */
\t\t\t\t\tsyslog(LOG_WARNING, "Blender3GS UI14 ICON BIND: id=%u", (unsigned)icongltex.id);
\t\t\t\t\tglBindTexture(GL_TEXTURE_2D, icongltex.id);
\t\t\t\t\tglPixelStorei(GL_UNPACK_ALIGNMENT, 4);'''
new_icon_text = unique_replace(orig_icons, old_icon, new_icon, 'icon null dispatch')
for path in (BLF, ICONS):
    back = path.with_name(path.name + '.' + BACKUP_TAG)
    if back.exists():
        stop('backup exists; refusing to overwrite: ' + str(back))
if not (TAG in new_blf_text and TAG in new_icon_text):
    stop('patch marker verification failed')

# Validate packager up front. No half-patched source when unknown fields.
pkg = PACK13.read_text()
pkg = unique_replace(pkg, 'Blender3GS-python-ui-v13-test.ipa', IPA.name, 'v13 IPA package output')
for key, value in (('CFBundleVersion', '14'), ('CFBundleShortVersionString', '0.14.0')):
    pattern = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(pattern, pkg)) != 1:
        stop('unexpected v13 packager field: ' + key)
    pkg = re.sub(pattern, lambda m: m.group(1) + repr(value), pkg, count=1)
if PACK14.exists() and PACK14.read_text() != pkg:
    stop('existing v14 packager differs; refusing overwrite')
print('PASS: both exact source changes and v14 packager prepared')

print('\n=== 3. BACK UP AND PATCH ONLY CURRENT UI13 SOURCES ===', flush=True)
for path in (BLF, ICONS):
    back = path.with_name(path.name + '.' + BACKUP_TAG)
    shutil.copy2(path, back)
    print('BACKUP:', back)
BLF.write_text(new_blf_text)
ICONS.write_text(new_icon_text)
print('PATCHED:', BLF)
print('PATCHED:', ICONS)
print('PRESERVED: font atlas 512, shadow change, Overlap, retained backing, Trackpad, Python/RNA/atexit')

if PREP:
    print('\nSUCCESS: UI14 PREPARE-ONLY (no build or IPA)')
    raise SystemExit(0)

WORK.mkdir(exist_ok=True, parents=True)
old_hash = sha(EXEC)
previous = WORK / 'Blender3GS-python-before-ui-v14-armv7'
if previous.exists():
    stop('existing v14 binary backup; verify build state before rerunning')
shutil.copy2(EXEC, previous)
print('BACKUP:', previous)

call('4. REBUILD FONT AND INTERFACE',
     ['ninja', '-C', BUILD, '-j4', 'bf_blenfont', 'bf_editor_interface'],
     WORK / 'ui-v14-build.log')
call('5. RELINK WITH PYTHON/RNA/ATEXIT', ['python3', LINK], WORK / 'ui-v14-link.log')
if sha(EXEC) == old_hash:
    stop('executable unchanged; refusing to package stale build')
call('6. VERIFY ARMv7', ['xcrun', 'lipo', '-info', EXEC], WORK / 'ui-v14-arch.log')
if 'armv7' not in (WORK / 'ui-v14-arch.log').read_text():
    stop('output is not armv7')
PACK14.write_text(pkg)
py_compile.compile(str(PACK14), doraise=True)
call('7. PACKAGE SEPARATE UI14 IPA', ['python3', PACK14], WORK / 'ui-v14-package.log')
if not IPA.is_file() or IPA.stat().st_size < 1000000:
    stop('v14 IPA missing/too small')
with zipfile.ZipFile(IPA) as z:
    error = z.testzip()
    if error:
        stop('invalid IPA ZIP member: ' + error)
    if 'Payload/Blender3GS.app/Blender3GS' not in z.namelist():
        stop('missing ARM executable in IPA')
print('\nSUCCESS: UI14 DEVICE TEST CANDIDATE:', IPA)
print('Expect log: Blender3GS UI14 ICON BIND, then UI12 ICONS')
print('Working Touch-v2 app and existing IPA files not modified.')