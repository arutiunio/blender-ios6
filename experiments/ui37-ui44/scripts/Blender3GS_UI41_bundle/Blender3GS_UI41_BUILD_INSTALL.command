#!/bin/bash
set -euo pipefail
cd "$HOME/Downloads"
PY="$PWD/Blender3GS_UI41_MEGA.py"
IPA="$PWD/Blender3GS-python-ui-v41-mega-first-frame.ipa"
BASE="$PWD/Blender3GS-python-ui-v40-native-first-frame.ipa"
MODE="${1:---build-install}"
case "$MODE" in
  --build-install|--resume|--check-only|--build-only|--install-only|--rollback) ;;
  *) echo 'Usage: bash Blender3GS_UI41_BUILD_INSTALL.command [--resume|--check-only|--build-only|--install-only|--rollback]' >&2; exit 2 ;;
esac
if [[ "$MODE" == --rollback ]]; then
  IPA="$BASE"
elif [[ "$MODE" != --install-only ]]; then
  [[ -s "$PY" ]] || { echo "ERROR: missing $PY (unzip UI41 first)" >&2; exit 1; }
  export DEVELOPER_DIR="/Applications/Xcode-26.6.app/Contents/Developer"
  [[ -d "$DEVELOPER_DIR" ]] || { echo "ERROR: Xcode 26.6 not found: $DEVELOPER_DIR" >&2; exit 1; }
  export IOS_SDKROOT="$(xcrun --sdk iphoneos --show-sdk-path)"
  [[ -n "$IOS_SDKROOT" ]] || { echo 'ERROR: iPhoneOS SDK not found' >&2; exit 1; }
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
[[ -s "$IPA" ]] || { echo "ERROR: IPA not found: $IPA" >&2; exit 1; }
if ! command -v ideviceinstaller >/dev/null 2>&1; then
  echo 'ERROR: missing ideviceinstaller. On Mac: brew install ideviceinstaller' >&2
  exit 1
fi
if ! command -v idevice_id >/dev/null 2>&1; then
  echo 'ERROR: missing idevice_id. On Mac: brew install libimobiledevice' >&2
  exit 1
fi
[[ -n "$(idevice_id -l | head -n1)" ]] || { echo 'ERROR: iPhone not detected over USB' >&2; exit 1; }
echo "=== INSTALL OVER USB (no ios6-installer / no SSH): $(basename "$IPA") ==="
ideviceinstaller install "$IPA"
echo '=== INSTALL REQUEST COMPLETED; launch from the iPhone Home screen ==='
