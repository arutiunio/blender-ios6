#!/usr/bin/env python3
"""Create a read-only, narrowly scoped Blender3GS UI19 source handoff ZIP.

Run on the Mac which built UI19. Does not build, patch, install, or upload.
The ZIP is for private source inspection, not a complete GPL source release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

MARKERS = (
    'BLENDER3GS_UI16_REAL_PROPERTIES_20260923',
    'BLENDER3GS_UI17_PROPERTIES_TEXT_20260923',
    'BLENDER3GS_UI18_NATIVE_ICON_TABS_20260923',
    'BLENDER3GS_UI19_HYBRID_TOUCH_20260924',
    'BLENDER3GS_UI_V12_20260923',
    'BLENDER3GS_UI_V13_20260923',
)
SOURCE_SUFFIXES = {'.c', '.h', '.cc', '.cpp', '.m', '.mm', '.glsl', '.vert', '.frag'}
SOURCE_DIRS = (
    'source/blender/editors/interface',
    'source/blender/editors/space_buttons',
    'source/blender/blenfont',
    'source/blender/windowmanager',
    'source/blender/editors/screen',
)
EXTRA_FILES = (
    'intern/ghost/intern/GHOST_WindowIOS.mm',
    'intern/ghost/intern/GHOST_WindowIOS.h',
    'source/blender/editors/space_view3d/space_view3d.c',
    'source/blender/editors/space_view3d/view3d_select.c',
    'CMakeLists.txt',
    'intern/ghost/CMakeLists.txt',
    'source/blender/editors/interface/CMakeLists.txt',
    'source/blender/editors/space_buttons/CMakeLists.txt',
)
REQUIRED = (
    'intern/ghost/intern/GHOST_WindowIOS.mm',
    'source/blender/windowmanager/intern/wm_files.c',
    'source/blender/editors/interface/interface_style.c',
    'source/blender/editors/space_buttons/buttons_header.c',
)
MAX_FILE_BYTES = 32 * 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def collect(src):
    found = {}
    for relative in SOURCE_DIRS:
        folder = src / relative
        if not folder.is_dir() or folder.is_symlink():
            continue
        for path in folder.rglob('*'):
            if (path.is_file() and not path.is_symlink()
                    and path.suffix.lower() in SOURCE_SUFFIXES
                    and not any(part.startswith('.') or '.before-' in part
                                for part in path.relative_to(src).parts)):
                found[path.relative_to(src).as_posix()] = path
    for relative in EXTRA_FILES:
        path = src / relative
        if path.is_file() and not path.is_symlink():
            found[relative] = path
    return dict(sorted(found.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / 'Downloads',
                        help='Directory containing blender-ios6-target')
    parser.add_argument('--output', type=Path,
                        help='New ZIP path (will not overwrite an existing file)')
    parser.add_argument('--check-only', action='store_true',
                        help='Audit available files and markers without creating a ZIP')
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    src = root / 'blender-ios6-target'
    if not src.is_dir():
        parser.error('missing modified source tree: ' + str(src))
    missing = [item for item in REQUIRED if not (src / item).is_file()]
    if missing:
        parser.error('required files are missing: ' + ', '.join(missing))
    files = collect(src)
    manifest = {'purpose': 'private UI19 source handoff; not a full release',
                'source_tree': 'blender-ios6-target', 'files': {},
                'build_artifacts': {}, 'warnings': []}
    for relative, path in files.items():
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            parser.error('source file unexpectedly large: ' + relative)
        data = path.read_bytes()
        markers = [tag for tag in MARKERS if tag.encode() in data]
        manifest['files'][relative] = {'sha256': hashlib.sha256(data).hexdigest(),
                                       'bytes': size, 'markers': markers}
    expected = {
        REQUIRED[0]: 'BLENDER3GS_UI19_HYBRID_TOUCH_20260924',
        REQUIRED[1]: 'BLENDER3GS_UI19_HYBRID_TOUCH_20260924',
        REQUIRED[2]: 'BLENDER3GS_UI17_PROPERTIES_TEXT_20260923',
        REQUIRED[3]: 'BLENDER3GS_UI16_REAL_PROPERTIES_20260923',
    }
    for relative, marker in expected.items():
        if marker not in manifest['files'][relative]['markers']:
            manifest['warnings'].append('Expected marker absent from ' + relative + ': ' + marker)
    for name in ('Blender3GS-python-armv7',
                 'Blender3GS-python-ui-v19-hybrid-touch.ipa'):
        path = root / name
        if path.is_file() and not path.is_symlink():
            manifest['build_artifacts'][name] = {'bytes': path.stat().st_size,
                                                 'sha256': digest(path)}
        else:
            manifest['warnings'].append('Build artifact not found: ' + name)
    print('Source files:', len(files))
    for warning in manifest['warnings']:
        print('WARNING:', warning)
    if args.check_only:
        print('CHECK ONLY: no files changed; no ZIP created')
        return 0
    output = (args.output.expanduser() if args.output else
              root / 'Blender3GS-ui19-source-handoff.zip').resolve()
    if output.exists():
        parser.error('output already exists; refusing to overwrite: ' + str(output))
    try:
        output.relative_to(src)
    except ValueError:
        pass
    else:
        parser.error('write the ZIP outside the modified source tree')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as archive:
            for relative, path in files.items():
                archive.write(path, arcname='blender-ios6-target/' + relative)
            archive.writestr('UI19-MANIFEST.json',
                             json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
        with zipfile.ZipFile(output) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError('ZIP CRC failed: ' + bad)
            if len(archive.namelist()) != len(files) + 1:
                raise RuntimeError('ZIP member count mismatch')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print('CREATED:', output)
    print('SHA256:', digest(output))
    print('Contains source files and hashes only; no IPA, logs, keys or provisioning profiles.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
