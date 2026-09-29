#!/bin/bash
set -euo pipefail
cd "$HOME/Downloads"
PY="$PWD/Blender3GS_UI44_FOCUS.py"
IPA="$PWD/Blender3GS-python-ui-v44-focus.ipa"
BASE="$PWD/Blender3GS-python-ui-v43-visual-diagnostic.ipa"
MODE="${1:---build-install}"
case "$MODE" in
  --build-install|--check-only|--resume|--package-only|--install-only|--rollback) ;;
  *) echo 'Usage: bash Blender3GS_UI44_BUILD_INSTALL.command [--check-only|--resume|--package-only|--install-only|--rollback]' >&2; exit 2;;
esac
if [[ "$MODE" == --rollback ]]; then
  IPA="$BASE"
elif [[ "$MODE" != --install-only ]]; then
  [[ -s "$PY" ]] || { echo "ERROR: missing $PY; unzip UI44 first" >&2; exit 1; }
  export DEVELOPER_DIR="/Applications/Xcode-26.6.app/Contents/Developer"
  [[ -d "$DEVELOPER_DIR" ]] || { echo "ERROR: Xcode missing $DEVELOPER_DIR" >&2; exit 1; }
  export IOS_SDKROOT="$(xcrun --sdk iphoneos --show-sdk-path)"
  [[ -n "$IOS_SDKROOT" ]] || { echo 'ERROR: iOS SDK unavailable' >&2; exit 1; }
  case "$MODE" in
    --check-only) python3 "$PY" --check-only; exit 0;;
    --resume) python3 "$PY" --resume --check-only; python3 "$PY" --resume;;
    --package-only) python3 "$PY" --package-only --check-only; python3 "$PY" --package-only;;
    *) python3 "$PY" --check-only; python3 "$PY";;
  esac
fi
[[ -s "$IPA" ]] || { echo "ERROR: missing IPA $IPA" >&2; exit 1; }
command -v ideviceinstaller >/dev/null || { echo 'ERROR: brew install ideviceinstaller' >&2; exit 1; }
command -v idevice_id >/dev/null || { echo 'ERROR: brew install libimobiledevice' >&2; exit 1; }
[[ -n "$(idevice_id -l | head -n 1)" ]] || { echo 'ERROR: iPhone not connected via USB' >&2; exit 1; }
echo "=== INSTALL $(basename "$IPA") VIA USB ==="
ideviceinstaller install "$IPA"
echo '=== Installation requested. Launch Blender; compare screenshot. ==='
