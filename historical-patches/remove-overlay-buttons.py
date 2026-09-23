#!/usr/bin/env python3
"""Remove Touch-v2 overlay buttons ONLY from the experimental Blender Py build.

Keep native Blender UI, all touch gestures, Python, GL4ES and atexit intact.
Do not alter the original Touch-v2 binary/IPA or build directory.
"""
from pathlib import Path
import hashlib
import os
import py_compile
import re
import shutil
import subprocess

ROOT = Path.home() / 'Downloads'
SOURCE = ROOT / 'blender-ios6-target/intern/ghost/intern/GHOST_WindowIOS.mm'
BUILD = ROOT / 'blender-ios6-build-python'
WORK = ROOT / 'blender-ios6-python'
BINARY = ROOT / 'Blender3GS-python-armv7'
LINKER = ROOT / 'blender-link-ios-python-v3.py'
PACKAGER = WORK / 'Blender3GS-package-nosplash.py'
NEW_PACKAGER = WORK / 'Blender3GS-package-cleanui.py'
IPA = ROOT / 'Blender3GS-python-cleanui-test.ipa'
MARKER = 'Blender3GS iOS6: native UI; no redundant overlay buttons'
BACKUP = SOURCE.with_name('GHOST_WindowIOS.mm.before-ios6-cleanui')
OLD_CONTROLS = '        [self installControls];'
OLD_AUTO = '        [self performSelector:@selector(autoMaximize) withObject:nil afterDelay:3.5];'


def stop(message):
    raise SystemExit('STOP: ' + message)


def section(message):
    print('\n========== ' + message + ' ==========', flush=True)


def run(label, command, log):
    section(label)
    print('COMMAND:', ' '.join(map(str, command)), flush=True)
    with log.open('w') as stream:
        result = subprocess.run([str(x) for x in command], stdout=stream,
                                stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        print(log.read_text(errors='replace')[-12000:], flush=True)
        stop('exit %s; log: %s' % (result.returncode, log))
    print('PASS:', log, flush=True)


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(part)
    return result.hexdigest()


section('1. PREFLIGHT EXPERIMENTAL BUILD')
for path in (SOURCE, BUILD / 'build.ninja', BINARY, LINKER, PACKAGER):
    if not path.is_file() or not path.stat().st_size:
        stop('missing/empty: ' + str(path))
    print('PASS:', path, flush=True)
if not os.environ.get('DEVELOPER_DIR') or not os.environ.get('IOS_SDKROOT'):
    stop('export DEVELOPER_DIR and IOS_SDKROOT first')
WORK.mkdir(exist_ok=True, parents=True)

section('2. REMOVE OVERLAY CREATION AND AUTOMATIC MAXIMIZE')
source = SOURCE.read_text()
if MARKER not in source:
    # Avoid affecting an unrelated GHOST source or the Python-disabled legacy port.
    if 'BLENDER_IOS6_GESTURES_V2' not in source:
        stop('expected Touch-v2 GHOST source marker missing; no changes')
    if source.count(OLD_CONTROLS) != 1 or source.count(OLD_AUTO) != 1:
        stop('expected Touch-v2 control/auto-maximize statements not found exactly once; no changes')
    # The two statements must belong to the same bindGhostSystem block.
    method_start = source.find('- (void)bindGhostSystem:(GHOST_SystemIOS *)system window:(GHOST_WindowIOS *)window\n{')
    method_end = source.find('\n- (UIButton *)newControl:', method_start)
    if method_start == -1 or method_end == -1:
        stop('unexpected bindGhostSystem implementation; no changes')
    method = source[method_start:method_end]
    if OLD_CONTROLS not in method or OLD_AUTO not in method:
        stop('control statements outside expected bindGhostSystem method; no changes')
    # Leave installControls, the gesture actions and the UIKit layer untouched;
    # with no creation m_viewButton remains nil (messages to nil are safe in Obj-C).
    new_method = method.replace(OLD_CONTROLS,
        '        /* ' + MARKER + '. Blender draws its own header now. */', 1)
    new_method = new_method.replace(OLD_AUTO,
        '        /* Do not auto-maximize: without VIEW button this traps the user in the viewport. */', 1)
    if BACKUP.exists():
        stop('backup exists without marker; inspect source before retry: ' + str(BACKUP))
    shutil.copy2(SOURCE, BACKUP)
    SOURCE.write_text(source[:method_start] + new_method + source[method_end:])
    print('PATCHED:', SOURCE, flush=True)
    print('BACKUP:', BACKUP, flush=True)
else:
    if source.count(MARKER) != 1 or OLD_CONTROLS in source[source.find('- (void)bindGhostSystem:'):source.find('- (UIButton *)newControl:')]:
        stop('patch marker present, but unexpected/partial modification; do not proceed')
    print('PASS: patch already applied', flush=True)
print('PASS: gesture handlers, native menu, OpenGL and UI source remain intact', flush=True)

run('3. REBUILD EXPERIMENTAL ARMv7 GHOST',
    ['ninja', '-C', BUILD, '-j4', 'bf_intern_ghost'], WORK / 'build-cleanui-ghost.log')

section('4. BACK UP AND RELINK PYTHON BINARY')
previous = WORK / 'Blender3GS-python-before-cleanui-armv7'
if not previous.exists():
    shutil.copy2(BINARY, previous)
print('BACKUP:', previous, flush=True)
old_digest = sha256(BINARY)
run('RELINK WITH EXISTING ATEXIT AND RNA FIXES',
    ['python3', LINKER], WORK / 'link-cleanui.log')
if sha256(BINARY) == old_digest:
    stop('binary hash unchanged after relink; refusing to package stale binary')
print('PASS: executable changed', flush=True)
run('5. VERIFY ARMv7', ['xcrun', 'lipo', '-info', BINARY], WORK / 'cleanui-arch.log')
nm = subprocess.run(['xcrun', 'nm', '-g', str(BINARY)], text=True, capture_output=True)
if nm.returncode or not re.search(r'\b[Tt]\s+_PyInit_atexit\b', nm.stdout):
    stop('new executable is missing PyInit_atexit')
print('PASS: PyInit_atexit present', flush=True)

section('6. PREPARE SEPARATE IPA')
package_source = PACKAGER.read_text()
old_name = 'Blender3GS-python-nosplash-test.ipa'
if package_source.count(old_name) != 1:
    stop('unexpected packager output name; previous IPAs untouched')
package_source = package_source.replace(old_name, IPA.name, 1)
for key, value in (('CFBundleVersion', '6'), ('CFBundleShortVersionString', '0.6.0')):
    expression = r"(info\['" + key + r"'\]\s*=\s*)'[^']+'"
    if len(re.findall(expression, package_source)) != 1:
        stop('unexpected packager version assignment: ' + key)
    package_source = re.sub(expression, lambda m: m.group(1) + repr(value),
                            package_source, count=1)
NEW_PACKAGER.write_text(package_source)
py_compile.compile(str(NEW_PACKAGER), doraise=True)
print('PASS:', NEW_PACKAGER, flush=True)
run('7. PACKAGE CLEAN NATIVE UI', ['python3', NEW_PACKAGER], WORK / 'package-cleanui.log')
if not IPA.is_file() or not IPA.stat().st_size:
    stop('new IPA not found')
section('SUCCESS: CLEAN UI EXPERIMENT READY')
print('IPA:', IPA, flush=True)
print('SIZE:', round(IPA.stat().st_size / 1024 / 1024, 2), 'MiB', flush=True)
print('Working Touch-v2 app and all earlier IPA files are unchanged.', flush=True)