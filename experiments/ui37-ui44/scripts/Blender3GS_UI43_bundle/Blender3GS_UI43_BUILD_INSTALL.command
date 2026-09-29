#!/bin/bash
set -euo pipefail
cd "$HOME/Downloads"
PY="$PWD/Blender3GS_UI43_VISUAL_PATCH.py"
IPA="$PWD/Blender3GS-python-ui-v43-visual-diagnostic.ipa"
BASE="$PWD/Blender3GS-python-ui-v41-mega-first-frame.ipa"
MODE="${1:---build-install}"
case "$MODE" in
  --build-install|--check-only|--resume|--build-only|--install-only|--rollback) ;;
  *) echo "Usage: bash Blender3GS_UI43_BUILD_INSTALL.command [--check-only|--resume|--build-only|--install-only|--rollback]" >&2; exit 2 ;;
esac
if [[ "$MODE" == --rollback ]]; then
  IPA="$BASE"
elif [[ "$MODE" != --install-only ]]; then
  [[ -s "$PY" ]] || { echo "ERROR: missing $PY; unzip UI43 first" >&2; exit 1; }
  export DEVELOPER_DIR="/Applications/Xcode-26.6.app/Contents/Developer"
  [[ -d "$DEVELOPER_DIR" ]] || { echo "ERROR: Xcode not found: $DEVELOPER_DIR" >&2; exit 1; }
  export IOS_SDKROOT="$(xcrun --sdk iphoneos --show-sdk-path)"
  [[ -n "$IOS_SDKROOT" ]] || { echo 'ERROR: iPhoneOS SDK unavailable' >&2; exit 1; }
  if [[ "$MODE" == --check-only ]]; then
    python3 "$PY" --check-only
    exit 0
  elif [[ "$MODE" == --resume ]]; then
    python3 "$PY" --resume --check-only
    python3 "$PY" --resume
  else
    python3 "$PY" --check-only
    python3 "$PY"
  fi
fi
[[ "$MODE" == --build-only ]] && exit 0
[[ -s "$IPA" ]] || { echo "ERROR: IPA missing: $IPA" >&2; exit 1; }
command -v ideviceinstaller >/dev/null 2>&1 || { echo 'ERROR: install ideviceinstaller: brew install ideviceinstaller' >&2; exit 1; }
command -v idevice_id >/dev/null 2>&1 || { echo 'ERROR: install libimobiledevice: brew install libimobiledevice' >&2; exit 1; }
[[ -n "$(idevice_id -l | head -n1)" ]] || { echo 'ERROR: no connected iPhone over USB' >&2; exit 1; }
echo "=== INSTALL $(basename "$IPA") THROUGH USB ==="
ideviceinstaller install "$IPA"
echo '=== Installation request completed; start Blender on iPhone ==='
