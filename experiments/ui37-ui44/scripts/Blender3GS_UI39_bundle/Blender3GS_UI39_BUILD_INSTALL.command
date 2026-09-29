#!/bin/bash
set -euo pipefail
cd "$HOME/Downloads"
SCRIPT="$PWD/Blender3GS_UI39_FAST_PROFILES.py"
CORE="$PWD/Blender3GS-python-ui-v39-3d-core.ipa"
FULL="$PWD/Blender3GS-python-ui-v39-full-direct-startup.ipa"
MODE="${1:---core}"
case "$MODE" in
 --core) PRESET=core; IPA="$CORE";;
 --full) PRESET=full; IPA="$FULL";;
 --install-core) PRESET=core; IPA="$CORE";;
 --install-full) PRESET=full; IPA="$FULL";;
 --build-only) PRESET=core; IPA="$CORE";;
 *) echo "USAGE: bash Blender3GS_UI39_BUILD_INSTALL.command [--core|--full|--install-core|--install-full|--build-only]";exit 1;;
esac
[ -s "$SCRIPT" ] || { echo 'ERROR: extract UI39 ZIP first';exit 1; }
if [[ "$MODE" != --install-* ]]; then
 python3 "$SCRIPT" --preset "$PRESET" --check-only
 if [[ ! -s "$IPA" ]]; then python3 "$SCRIPT" --preset "$PRESET"; else
  echo "EXISTING IPA: $IPA; use --install-$PRESET to install it or move the IPA away before rebuilding."
 fi
fi
[[ "$MODE" != --build-only ]] || exit 0
[ -s "$IPA" ] || { echo "ERROR: missing $IPA";exit 1; }
command -v iproxy >/dev/null || { echo 'ERROR: iproxy missing';exit 1; }
STARTED=0;PROXY=''
cleanup(){ if [ "$STARTED" = 1 ] && [ -n "$PROXY" ]; then kill "$PROXY" 2>/dev/null || true;fi; }
trap cleanup EXIT
if ! nc -z 127.0.0.1 2222 >/dev/null 2>&1;then
 iproxy 2222:22 > "$HOME/Downloads/Blender3GS-ui39-iproxy.log" 2>&1 & PROXY=$!;STARTED=1;sleep 2
fi
nc -z 127.0.0.1 2222 || { echo 'ERROR: no USB SSH tunnel';exit 1; }
echo '=== COPY UI39 IPA ==='
scp -O -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -P 2222 "$IPA" root@127.0.0.1:/private/var/tmp/
echo '=== INSTALL UI39 ==='
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -p 2222 root@127.0.0.1 "/private/var/tmp/ios6-installer install /private/var/tmp/$(basename "$IPA")"
echo "=== UI39 $PRESET INSTALL FINISHED ==="
