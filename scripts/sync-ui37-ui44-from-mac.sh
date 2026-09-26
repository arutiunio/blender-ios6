#!/usr/bin/env bash
# Upload only the source-matched UI37–UI44 development scripts and screenshots.
# Run this on the development Mac, not on the iPhone. No IPA or raw syslogs.
set -euo pipefail

REPO="https://github.com/arutiunio/blender-ios6.git"
BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_ROOT="${1:-$SCRIPT_DIR}"
PACK_ROOT="$(cd "$PACK_ROOT" && pwd)"
CHECKSUMS="$SCRIPT_DIR/../experiments/ui37-ui44/SHA256SUMS"

if ! command -v git >/dev/null || ! command -v python3 >/dev/null || ! command -v shasum >/dev/null; then
  echo "STOP: git, python3 and shasum are required." >&2
  exit 1
fi
if ! git config --global user.name >/dev/null || ! git config --global user.email >/dev/null; then
  echo "STOP: configure git user.name and user.email before committing." >&2
  exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/blender3gs-ui44-sync.XXXXXX")"
echo "Staging in $WORK"
git clone --depth 1 --branch "$BRANCH" "$REPO" "$WORK/repo"
DEST="$WORK/repo/experiments/ui37-ui44"
mkdir -p "$DEST/bundles" "$DEST/screenshots" "$DEST/scripts"

# Prefer the separately downloaded one-file upload pack; fall back to ~/Downloads.
python3 - "$PACK_ROOT" "$HOME/Downloads" "$CHECKSUMS" "$DEST" <<'PY'
import hashlib, pathlib, shutil, sys, zipfile
root, downloads, sums, dest = map(pathlib.Path, sys.argv[1:])
wanted = []
for raw in sums.read_text().splitlines():
    if not raw or raw.startswith('#'): continue
    digest, relative = raw.split(None, 1)
    relative = relative.strip()
    assert relative.startswith(('bundles/', 'screenshots/'))
    wanted.append((digest, pathlib.Path(relative)))

missing = []
for digest, relative in wanted:
    name = relative.name
    candidates = [root / relative, root / name, downloads / name]
    source = next((x for x in candidates if x.is_file()), None)
    if source is None:
        missing.append(name)
        continue
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit('STOP: checksum mismatch: ' + str(source))
    target = dest / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
if missing:
    raise SystemExit('STOP: missing files. Download the upload pack or supply: ' + ', '.join(missing))

for _, relative in wanted:
    if relative.suffix != '.zip': continue
    with zipfile.ZipFile(dest / relative) as archive:
        targetdir = dest / 'scripts' / relative.stem
        targetdir.mkdir(parents=True, exist_ok=True)
        for info in archive.infolist():
            # The original patch bundles have only plain top-level files.
            p = pathlib.PurePosixPath(info.filename)
            if info.is_dir(): continue
            if len(p.parts) != 1 or p.name.startswith('.'):
                raise SystemExit('STOP: unsafe/unknown archive entry: ' + info.filename)
            (targetdir / p.name).write_bytes(archive.read(info))
print('PASS: copied and verified', len(wanted), 'original files; extracted all patch scripts')
PY

(
  cd "$DEST"
  shasum -a 256 -c SHA256SUMS
)
cd "$WORK/repo"
git add -- experiments/ui37-ui44
if git diff --cached --quiet; then
  echo "No changes: all assets are already committed."
  exit 0
fi
git commit -m "archive: add UI37-UI44 source patch bundles and device screenshots"
git push origin HEAD:"$BRANCH"
echo "SUCCESS: https://github.com/arutiunio/blender-ios6/tree/main/experiments/ui37-ui44"
echo "Uploaded original archives, extracted scripts and screenshots. No IPA, credentials or raw syslogs."
