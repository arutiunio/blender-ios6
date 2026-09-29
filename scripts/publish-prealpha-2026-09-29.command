#!/usr/bin/env bash
set -euo pipefail

REPO="arutiunio/blender-ios6"
TAG="pre-alpha-2026-09-29"
TITLE="Blender 3GS pre-alpha snapshot — UI43 build / UI44 dev patch"
DL="$HOME/Downloads"
HANDOFF="$DL/Blender3GS_RELEASE_HANDOFF.zip"
DEPS="$DL/Blender3GS_RELEASE_DEPS_HANDOFF.tar.gz"
UI44="$DL/Blender3GS_UI44_bundle.zip"
UPLOAD_PACK="$DL/Blender3GS_UI37_UI44_GitHub_upload_pack.zip"

command -v gh >/dev/null || { echo "STOP: gh is not installed"; exit 1; }
gh auth status -h github.com >/dev/null || { echo "STOP: run gh auth login first"; exit 1; }
[[ -f "$HANDOFF" ]] || { echo "STOP: missing $HANDOFF"; exit 1; }
[[ -f "$DEPS" ]] || { echo "STOP: missing $DEPS"; exit 1; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/blender3gs-release.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
unzip -q "$HANDOFF" -d "$TMP"
HD="$TMP/Blender3GS_RELEASE_HANDOFF"
IPA="$HD/Blender3GS-python-ui-v43-visual-diagnostic.ipa"
SOURCE="$HD/Blender3GS-current-source.tar.gz"
[[ -f "$IPA" ]] || { echo "STOP: IPA not found inside handoff"; exit 1; }
[[ -f "$SOURCE" ]] || { echo "STOP: source tarball not found inside handoff"; exit 1; }

SUMS="$TMP/Blender3GS-prealpha-2026-09-29-SHA256SUMS.txt"
{
  shasum -a 256 "$IPA"
  shasum -a 256 "$SOURCE"
  shasum -a 256 "$HANDOFF"
  shasum -a 256 "$DEPS"
  [[ -f "$UI44" ]] && shasum -a 256 "$UI44"
  [[ -f "$UPLOAD_PACK" ]] && shasum -a 256 "$UPLOAD_PACK"
} | sed "s#${HD}/##; s#${DL}/##" > "$SUMS"

NOTES="$TMP/RELEASE_NOTES.md"
cat > "$NOTES" <<'EOF'
# Blender 3GS — pre-alpha snapshot

This is an **experimental, rough development snapshot** of Blender 2.64 running natively on a jailbroken **iPhone 3GS / iOS 6.1.6 / ARMv7**. It is published early so the working state, source and build archaeology are not lost.

## What is in this release

- `Blender3GS-python-ui-v43-visual-diagnostic.ipa` — current packaged/tested UI43 application (`io.arutiunio.blender3gs.python`).
- `Blender3GS-current-source.tar.gz` — matching development source snapshot. It contains UI40/UI41 fast-start work and UI43 graphics isolation markers. **It does not contain the later UI44 patch applied as a built IPA.**
- `Blender3GS_RELEASE_HANDOFF.zip` — source snapshot plus build/package scripts and development helpers collected from the Mac.
- `Blender3GS_RELEASE_DEPS_HANDOFF.tar.gz` — large, dirty developer dependency/build snapshot: CPython trees, iOS static libraries, GL4ES artifacts, old ARMv7 binaries, build logs and linker/build state. This is for archaeology/reproduction, not a clean SDK.
- `Blender3GS_UI44_bundle.zip` (when present) — newer **unverified** UI44 patch/build scripts. No UI44 IPA is claimed here.
- `Blender3GS_UI37_UI44_GitHub_upload_pack.zip` (when present) — archived UI37–UI44 patch bundles and screenshots already mirrored into the repository.
- SHA-256 manifest for the release assets.

## Current behavior

UI40/UI41 moved the first real 3D Viewport presentation before embedded Python startup. UI43 then isolated the problematic legacy Camera/Lamp viewport helper path: the giant white triangle/camera rectangle seen in earlier builds disappeared in the device screenshot, but white cross-editor lines and icon/UI artifacts remain.

The UI is intentionally reduced compared with desktop Blender. A tested Core profile reached about 119 registered panels; an earlier full-profile run reached 227. Python initialization still stalls the main thread after the early native frame. Background/resume is not fixed: process IDs changed after returning from Home in prior tests.

## Known problems

- visual corruption remains in parts of the Viewport/Outliner/Properties UI;
- Camera/Lamp viewport helpers are suppressed/experimental rather than fully fixed;
- UI44 is source-patch-only in this snapshot and has not been verified on the phone;
- first cold launch is slower than warm launches;
- no guarantee of background process persistence;
- complex project save/load, final rendering, add-ons and long sessions are not fully validated;
- this is jailbreak-only software and is not an App Store build.

## Installation target

- iPhone 3GS
- iOS 6.1.6
- ARMv7
- jailbroken device with a compatible IPA installation path/AppSync setup

Do **not** treat this as a stable Blender distribution. Keep a backup and expect crashes, missing UI and graphics bugs.

## Source / history

Repository: https://github.com/arutiunio/blender-ios6

UI37–UI44 archive and screenshots: https://github.com/arutiunio/blender-ios6/tree/main/experiments/ui37-ui44

This release is intentionally marked **pre-release**.
EOF

ASSETS=("$IPA" "$SOURCE" "$HANDOFF" "$DEPS" "$SUMS")
[[ -f "$UI44" ]] && ASSETS+=("$UI44")
[[ -f "$UPLOAD_PACK" ]] && ASSETS+=("$UPLOAD_PACK")

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "Release exists; updating notes and replacing assets..."
  gh release edit "$TAG" --repo "$REPO" --title "$TITLE" --notes-file "$NOTES" --prerelease
  gh release upload "$TAG" "${ASSETS[@]}" --repo "$REPO" --clobber
else
  echo "Creating prerelease $TAG..."
  gh release create "$TAG" "${ASSETS[@]}" --repo "$REPO" --target main --title "$TITLE" --notes-file "$NOTES" --prerelease
fi

echo
echo "SUCCESS"
gh release view "$TAG" --repo "$REPO" --json url,name,tagName,isPrerelease --jq '.url'
