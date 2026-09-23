#!/usr/bin/env python3
"""Package Python-enabled Blender3GS as a separate iOS 6 IPA.

Run on the Mac after successfully linking Blender3GS-python-armv7.
This script never modifies the original IPA, installed app, or working build.
"""
from pathlib import Path
import hashlib
import os
import plistlib
import shutil
import subprocess
import sys
import zipfile

root = Path.home() / 'Downloads'
backup_ipa = root / 'Blender3GS-working-backup/Blender3GS-touch-v2.ipa'
working_ipa = root / 'Blender3GS-touch-v2.ipa'
source_binary = root / 'Blender3GS-python-armv7'
python_tree = root / 'blender-ios6-build-python/source/creator/python/lib/python3.3'
source_stdlib = root / 'blender-ios6-python/src/Python-3.3.7/Lib'
project = root / 'Blender3GS-python-package'
payload = project / 'Payload'
app = payload / 'Blender3GS.app'
output_ipa = root / 'Blender3GS-python-test.ipa'
bundle_id = 'io.arutiunio.blender3gs.python'


def stop(message):
    raise SystemExit('STOP: ' + message)


def need(path, label):
    if not path.is_file():
        stop(f'{label} missing: {path}')
    print('PASS:', label, path)


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def command(args, *, cwd=None):
    p = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.stdout.strip():
        print(p.stdout.rstrip())
    if p.returncode:
        stop('Command failed (%d): %s' % (p.returncode, ' '.join(map(str, args))))
    return p.stdout


print('=== 1. VERIFY SOURCES ===')
need(source_binary, 'Python-enabled executable')
need(python_tree / 'encodings/__init__.py', 'Extracted Python 3.3 encodings')
need(python_tree / 'importlib/__init__.py', 'Extracted Python 3.3 importlib')
need(python_tree / 'os.py', 'Extracted Python 3.3 os.py')
need(python_tree / 'site.py', 'Extracted Python 3.3 site.py')
need(source_stdlib / 'encodings/__init__.py', 'CPython source stdlib')

ipa = next((x for x in (backup_ipa, working_ipa) if x.is_file()), None)
if ipa is None:
    stop('Working Touch v2 IPA not found; supply one of: ' +
         str(backup_ipa) + ' or ' + str(working_ipa))
need(ipa, 'Unmodified working Touch v2 IPA')

lipo = shutil.which('lipo') or '/usr/bin/lipo'
command([lipo, '-info', source_binary])
file_output = command(['/usr/bin/file', source_binary])
if 'Mach-O executable arm_v7' not in file_output:
    stop('New Blender executable is not ARMv7 Mach-O')

with zipfile.ZipFile(ipa) as z:
    bad = z.testzip()
    if bad:
        stop('Working IPA has a corrupt member: ' + bad)
    names = set(z.namelist())
    required = ('Payload/Blender3GS.app/Info.plist',
                'Payload/Blender3GS.app/Blender3GS',
                'Payload/Blender3GS.app/2.64/scripts/startup/bl_ui/__init__.py')
    missing = [name for name in required if name not in names]
    if missing:
        stop('Working IPA is missing required Blender resources: ' + repr(missing))
    if any(name.startswith('/') or '..' in Path(name).parts for name in names):
        stop('Unsafe path in source IPA')
print('Source IPA:', ipa)

print('\n=== 2. CREATE SEPARATE PACKAGE ===')
# This is an isolated *experimental* output. Never remove Blender3GS-package.
if project.exists():
    shutil.rmtree(project)
project.mkdir(parents=True)
command(['/usr/bin/unzip', '-q', str(ipa), '-d', str(project)])
need(app / 'Blender3GS', 'Extracted original executable')
if not (app / '2.64/scripts/startup/bl_ui/__init__.py').is_file():
    stop('bl_ui scripts not extracted')

shutil.copy2(source_binary, app / 'Blender3GS')
(app / 'Blender3GS').chmod(0o755)
if sha256(source_binary) != sha256(app / 'Blender3GS'):
    stop('Executable was not copied faithfully')
print('PASS: new Python-enabled executable replaces only the STAGING copy')

print('\n=== 3. INSTALL PYTHON STANDARD LIBRARY ===')
# Blender 2.64 macOS layout: 2.64/python/lib/python3.3/encodings, os.py, etc.
python_destination = app / '2.64/python/lib/python3.3'
if python_destination.exists():
    shutil.rmtree(python_destination)
shutil.copytree(python_tree, python_destination)
for name in ('encodings/__init__.py', 'importlib/__init__.py', 'os.py', 'site.py'):
    need(python_destination / name, 'Packaged Python: ' + name)
files = sum(1 for p in python_destination.rglob('*') if p.is_file())
print('Python stdlib files:', files)
if files < 500:
    stop('Unusually small Python standard library; stop before signing')
ui = app / '2.64/scripts/startup/bl_ui'
print('Blender bl_ui .py files:', sum(1 for p in ui.rglob('*.py')))

print('\n=== 4. SEPARATE APP ID; PRESERVE TOUCH RESOURCES ===')
plist = app / 'Info.plist'
with plist.open('rb') as f:
    info = plistlib.load(f)
if info.get('CFBundleExecutable') != 'Blender3GS':
    stop('Unexpected executable name in original Info.plist')
original_id = info.get('CFBundleIdentifier', '(unknown)')
if original_id == bundle_id:
    stop('Test bundle identifier matches the original: ' + bundle_id)
info['CFBundleIdentifier'] = bundle_id
info['CFBundleDisplayName'] = 'Blender Py'
info['CFBundleName'] = 'Blender3GSPy'
info['CFBundleVersion'] = '2'
info['CFBundleShortVersionString'] = '0.2.0'
with plist.open('wb') as f:
    plistlib.dump(info, f, fmt=plistlib.FMT_XML)
print('Original app ID:', original_id)
print('Test app ID:    ', bundle_id)

# A copy from an IPA could have a signature from an earlier build.
shutil.rmtree(app / '_CodeSignature', ignore_errors=True)
(app / 'CodeResources').unlink(missing_ok=True)

print('\n=== 5. SIGN NEW BINARY ===')
ldid = shutil.which('ldid')
if ldid is None:
    stop('ldid not found in PATH; no IPA has been created')
command([ldid, '-S', app / 'Blender3GS'])
command(['/usr/bin/file', app / 'Blender3GS'])

print('\n=== 6. BUILD AND VERIFY IPA ===')
if output_ipa.exists():
    output_ipa.unlink()
command(['/usr/bin/zip', '-qry', str(output_ipa), 'Payload'], cwd=project)
with zipfile.ZipFile(output_ipa) as z:
    bad = z.testzip()
    if bad:
        stop('New IPA has corrupt member: ' + bad)
    names = set(z.namelist())
    required = (
        'Payload/Blender3GS.app/Blender3GS',
        'Payload/Blender3GS.app/Info.plist',
        'Payload/Blender3GS.app/2.64/scripts/startup/bl_ui/__init__.py',
        'Payload/Blender3GS.app/2.64/python/lib/python3.3/encodings/__init__.py',
        'Payload/Blender3GS.app/2.64/python/lib/python3.3/os.py',
        'Payload/Blender3GS.app/2.64/datafiles/bfont.ttf',
    )
    missing = [name for name in required if name not in names]
    if missing:
        stop('Packaged IPA missing important resources: ' + repr(missing))
    packaged_plist = plistlib.loads(z.read('Payload/Blender3GS.app/Info.plist'))
    if packaged_plist['CFBundleIdentifier'] != bundle_id:
        stop('IPA has unexpected bundle identifier')
print('PASS: IPA structure and Python resources verified')
print('IPA:', output_ipa)
print('IPA size:', round(output_ipa.stat().st_size / 1024**2, 2), 'MiB')
print('Working IPA and installed Touch v2 were not modified')
print('READY FOR DEVICE TEST — Python startup/bl_ui is not yet verified')