#!/bin/bash
set -euo pipefail
cd "$HOME/Downloads"
SCRIPT="$PWD/Blender3GS-ui-v37-stage-and-icons.py"
IPA="$PWD/Blender3GS-python-ui-v37-staged-full-ui-buffer-icons.ipa"
[ -s "$SCRIPT" ] || { echo 'ERROR: unzip UI37 bundle first'; exit 1; }
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode-26.6.app/Contents/Developer}"
if [ "${1:-}" != '--install-only' ]; then
    export IOS_SDKROOT="$(xcrun --sdk iphoneos --show-sdk-path)"
    if [ "${1:-}" = '--resume' ]; then python3 "$SCRIPT" --resume
    else python3 "$SCRIPT" --check-only && python3 "$SCRIPT"; fi
fi
[ -s "$IPA" ] || { echo "ERROR: missing $IPA"; exit 1; }
command -v iproxy >/dev/null || { echo 'ERROR: iproxy missing'; exit 1; }
STARTED=0; PROXY=''
cleanup() { if [ "$STARTED" = 1 ] && [ -n "$PROXY" ]; then kill "$PROXY" 2>/dev/null || true; fi; }
trap cleanup EXIT
if ! nc -z 127.0.0.1 2222 >/dev/null 2>&1; then
    iproxy 2222:22 > "$HOME/Downloads/Blender3GS-ui37-iproxy.log" 2>&1 &
    PROXY=$!; STARTED=1; sleep 2
fi
nc -z 127.0.0.1 2222 || { echo 'ERROR: USB tunnel unavailable'; exit 1; }
echo '=== COPY UI37 IPA ==='
scp -O -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -P 2222 "$IPA" root@127.0.0.1:/private/var/tmp/
echo '=== INSTALL UI37 ==='
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -p 2222 root@127.0.0.1 "/private/var/tmp/ios6-installer install /private/var/tmp/$(basename "$IPA")"
echo '=== UI37 INSTALL COMMAND FINISHED ==='
