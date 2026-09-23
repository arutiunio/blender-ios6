#!/usr/bin/env python3
"""Repair missing built-in CPython 3.3 atexit for experimental Blender3GS.

Run on the user's Mac from ~/Downloads. Changes experimental Blender source,
creates separate object/linker/IPA, never modifies the working Touch v2 app.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

ROOT = Path.home() / 'Downloads'
SRC = ROOT / 'blender-ios6-target'
BUILD = ROOT / 'blender-ios6-build-python'
WORK = ROOT / 'blender-ios6-python'
PYTHON = WORK / 'src/Python-3.3.7'
DEPS = ROOT / 'ios-deps/python33'
BPy = SRC / 'source/blender/python/intern/bpy_interface.c'
ATEXIT_SRC = PYTHON / 'Modules/atexitmodule.c'
ATEXIT_OBJ = WORK / 'atexitmodule-ios6.o'
LINK_V2 = ROOT / 'blender-link-ios-python-v2.py'
LINK_V3 = ROOT / 'blender-link-ios-python-v3.py'
PACKAGER = ROOT / 'Blender3GS-package-python.py'
PACKAGER_V3 = WORK / 'Blender3GS-package-atexit.py'
BINARY = ROOT / 'Blender3GS-python-armv7'
IPA = ROOT / 'Blender3GS-python-atexit-test.ipa'
MARKER = 'Blender3GS iOS6: register built-in atexit before Py_Initialize'


def stop(message):
    raise SystemExit('STOP: ' + message)


def execute(args, *, log=None):
    args = [str(x) for x in args]
    if log:
        with log.open('w') as stream:
            p = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT,
                               text=True)
        result = log.read_text(errors='replace')
    else:
        p = subprocess.run(args, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
        result = p.stdout
    if p.returncode:
        if log:
            lines = result.splitlines()
            matches = [i for i, line in enumerate(lines) if re.search(
                r'FAILED:|fatal error:|error:|Undefined symbols|ninja: error:', line)]
            print('\n=== FIRST ERRORS ===')
            for i in matches[:5]:
                print('\n'.join(lines[max(i-1, 0):i+6])); print('---')
            print('\n=== LAST 45 LINES ===')
            print('\n'.join(lines[-45:]))
        else:
            print(result[-12000:])
        stop('Command failed: ' + ' '.join(args) + (f'\nLog: {log}' if log else ''))
    return result


print('=== 1. VERIFY ORIGINAL INPUTS ===')
for path in (BPy, ATEXIT_SRC, DEPS / 'include/python3.3m/Python.h',
             DEPS / 'include/python3.3m/pyconfig.h',
             DEPS / 'lib/libpython3.3m.a', LINK_V2, PACKAGER,
             BUILD / 'lib/libbf_python.a', BINARY):
    if not path.is_file():
        stop(f'Missing: {path}')
    print('PASS:', path.name)

if not os.environ.get('DEVELOPER_DIR'):
    stop('Export DEVELOPER_DIR=/Applications/Xcode-26.6.app/Contents/Developer')

sdk = execute(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path']).strip()
clang = execute(['xcrun', '--sdk', 'iphoneos', '--find', 'clang']).strip()
if not Path(sdk).is_dir() or not Path(clang).is_file():
    stop('iPhoneOS SDK or Clang not found')
WORK.mkdir(parents=True, exist_ok=True)

print('\n=== 2. COMPILE REAL CPYTHON ATEXIT MODULE FOR ARMV7 ===')
execute([
    clang, '--target=armv7-apple-ios6.0', '-arch', 'armv7',
    '-miphoneos-version-min=6.0', '-isysroot', sdk,
    '-I' + str(DEPS / 'include/python3.3m'),
    '-O2', '-funsigned-char', '-c', ATEXIT_SRC,
    '-o', ATEXIT_OBJ,
], log=WORK / 'build-atexit-ios6.log')
arch = execute(['xcrun', 'lipo', '-info', ATEXIT_OBJ]).strip()
nms = execute(['xcrun', 'nm', '-g', ATEXIT_OBJ])
print(arch)
if 'armv7' not in arch or not re.search(r'(?m)^\s*[0-9a-fA-F]+\s+T\s+_PyInit_atexit\s*$', nms):
    stop('atexit object is not ARMv7 with exported PyInit_atexit')
print('PASS: genuine CPython PyInit_atexit compiled')

print('\n=== 3. REGISTER MODULE BEFORE Py_Initialize ===')
s = BPy.read_text()
if MARKER not in s:
    target = re.search(r'(?m)^[ \t]*Py_Initialize\(\);[ \t]*$', s)
    if not target or len(re.findall(r'(?m)^[ \t]*Py_Initialize\(\);[ \t]*$', s)) != 1:
        stop('Expected exactly one standalone Py_Initialize();. Source unchanged.')
    indent = re.match(r'[ \t]*', target.group()).group()
    patch = (
        f'{indent}/* {MARKER} */\n'
        f'{indent}#ifdef WITH_IOS\n'
        f'{indent}{{\n'
        f'{indent}    extern PyObject *PyInit_atexit(void);\n'
        f'{indent}    if (PyImport_AppendInittab("atexit", PyInit_atexit) != 0) {{\n'
        f'{indent}        Py_FatalError("Blender3GS: cannot register built-in atexit");\n'
        f'{indent}    }}\n'
        f'{indent}}}\n'
        f'{indent}#endif\n\n'
    )
    backup = BPy.with_name('bpy_interface.c.before-ios6-atexit')
    if not backup.exists():
        shutil.copy2(BPy, backup)
    probe = (
        f'\n{indent}#ifdef WITH_IOS\n'
        f'{indent}{{\n'
        f'{indent}    PyObject *ios6_atexit_probe = PyImport_ImportModule("atexit");\n'
        f'{indent}    if (ios6_atexit_probe == NULL) {{\n'
        f'{indent}        PyErr_Print();\n'
        f'{indent}        Py_FatalError("Blender3GS: atexit import failed after Py_Initialize");\n'
        f'{indent}    }}\n'
        f'{indent}    Py_DECREF(ios6_atexit_probe);\n'
        f'{indent}}}\n'
        f'{indent}#endif\n'
    )
    BPy.write_text(s[:target.start()] + patch + s[target.start():target.end()] + probe + s[target.end():])
    print('PATCHED:', BPy)
    print('BACKUP:', backup)
else:
    print('ALREADY PATCHED:', BPy)

print('\n=== 4. REBUILD BLENDER PYTHON ARCHIVE ===')
execute(['ninja', '-C', BUILD, '-j4', 'bf_python'],
        log=WORK / 'build-blender-atexit.log')
archive_nm = execute(['xcrun', 'nm', '-u', BUILD / 'lib/libbf_python.a'])
if '_PyImport_AppendInittab' not in archive_nm or '_PyInit_atexit' not in archive_nm:
    stop('Rebuilt Blender Python archive does not reference both module registration symbols')
print('PASS: bf_python rebuilt and references atexit registration')

print('\n=== 5. CREATE SEPARATE LINKER V3 ===')
linker = LINK_V2.read_text()
needle = 'with log_path.open("w") as stream:'
if linker.count(needle) != 1 or 'argv.insert(2, str(rna_fallback))' not in linker:
    stop('Unexpected V2 linker layout. Existing linker unchanged.')
new_part = '''# Blender3GS: actual CPython 3.3 native atexit module (armv7).
atexit_object = home / "Downloads/blender-ios6-python/atexitmodule-ios6.o"
if not atexit_object.is_file():
    raise SystemExit(f"Missing CPython atexit object: {atexit_object}")
argv.insert(2, str(atexit_object))
print("CPython atexit:", atexit_object)

'''
LINK_V3.write_text(linker.replace(needle, new_part + needle, 1))
execute([sys.executable, '-m', 'py_compile', LINK_V3])
print('PASS:', LINK_V3)

print('\n=== 6. LINK EXPERIMENTAL BLENDER WITH ATEXIT ===')
execute([sys.executable, LINK_V3], log=WORK / 'link-blender-atexit-run.log')
print('\n'.join((WORK / 'link-blender-atexit-run.log').read_text(
    errors='replace').splitlines()[-33:]))
if not BINARY.is_file():
    stop('Linked binary missing')
nm_binary = execute(['xcrun', 'nm', '-g', BINARY])
if not re.search(r'(?m)^\s*[0-9a-fA-F]+\s+T\s+_PyInit_atexit\s*$', nm_binary):
    stop('Final executable lacks PyInit_atexit')
print('PASS: final ARMv7 executable defines PyInit_atexit')
print(execute(['xcrun', 'lipo', '-info', BINARY]).strip())

print('\n=== 7. PACKAGE NEW IPA, KEEP PREVIOUS TEST IPA ===')
package_text = PACKAGER.read_text()
old_filename = "output_ipa = root / 'Blender3GS-python-test.ipa'"
new_filename = "output_ipa = root / 'Blender3GS-python-atexit-test.ipa'"
old_ver = "info['CFBundleVersion'] = '2'"
old_short = "info['CFBundleShortVersionString'] = '0.2.0'"
if (package_text.count(old_filename) != 1 or
        package_text.count(old_ver) != 1 or
        package_text.count(old_short) != 1):
    stop('Unexpected original packager layout; IPA packaging skipped, linked binary is ready.')
package_text = (package_text.replace(old_filename, new_filename, 1)
                .replace(old_ver, "info['CFBundleVersion'] = '3'", 1)
                .replace(old_short, "info['CFBundleShortVersionString'] = '0.3.0'", 1))
PACKAGER_V3.write_text(package_text)
execute([sys.executable, '-m', 'py_compile', PACKAGER_V3])
execute([sys.executable, PACKAGER_V3], log=WORK / 'package-blender-atexit.log')
print('\n'.join((WORK / 'package-blender-atexit.log').read_text(
    errors='replace').splitlines()[-13:]))
if not IPA.is_file() or IPA.stat().st_size < 1024 * 1024:
    stop('New IPA missing or unusually small')
print('\nSUCCESS:', IPA)
print('Working Touch v2 and earlier Blender Py test IPA were not modified.')
print('Ready for device test. Python initialization and bl_ui are not yet verified.')