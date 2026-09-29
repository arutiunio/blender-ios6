#!/bin/bash
set -euo pipefail
cd "$HOME/Downloads"
PY="$PWD/Blender3GS_UI40_FIXED_NATIVE_PREVIEW.py"
IPA="$PWD/Blender3GS-python-ui-v40-native-first-frame.ipa"
MODE="${1:---build-install}"
case "$MODE" in
  --build-install|--build-only|--resume|--check-only|--install-only) ;;
  *) echo 'Usage: bash Blender3GS_UI40_FIXED_BUILD_INSTALL.command [--build-install|--resume|--build-only|--check-only|--install-only]'; exit 2;;
esac
if [[ "$MODE" != --install-only ]]; then
  [[ -s "$PY" ]] || { echo "ERROR: extract Blender3GS_UI40_bundle.zip first"; exit 1; }
  export DEVELOPER_DIR="/Applications/Xcode-26.6.app/Contents/Developer"
  export IOS_SDKROOT="$(xcrun --sdk iphoneos --show-sdk-path)"
  if [[ "$MODE" == --check-only ]]; then
    python3 "$PY" --check-only
    exit
  elif [[ "$MODE" == --resume ]]; then
    python3 "$PY" --resume --check-only
    python3 "$PY" --resume
  else
    python3 "$PY" --check-only
    python3 "$PY"
  fi
fi
[[ "$MODE" == --build-only ]] && exit 0
[[ -s "$IPA" ]] || { echo "ERROR: missing $IPA"; exit 1; }
command -v iproxy >/dev/null || { echo 'ERROR: missing iproxy'; exit 1; }
STARTED=0; PROXY=''
cleanup() { if [[ "$STARTED" == 1 && -n "$PROXY" ]]; then kill "$PROXY" 2>/dev/null || true; fi; }
trap cleanup EXIT
if ! nc -z 127.0.0.1 2222 >/dev/null 2>&1; then
  iproxy 2222:22 > "$HOME/Downloads/Blender3GS-ui40-iproxy.log" 2>&1 & PROXY=$!; STARTED=1
  sleep 2
fi
nc -z 127.0.0.1 2222 || { echo 'ERROR: no USB SSH tunnel'; exit 1; }
echo '=== COPY UI40 IPA TO IPHONE ==='
scp -O -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -P 2222 "$IPA" root@127.0.0.1:/private/var/tmp/
echo '=== INSTALL UI40 ==='
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -p 2222 root@127.0.0.1 \
  "/private/var/tmp/ios6-installer install /private/var/tmp/$(basename "$IPA")"
echo '=== UI40 INSTALL COMMAND FINISHED ==='
