#!/bin/bash
# iPhone 3GS (iOS 6): press Home + Power, then run this on Mac with iproxy 2222:22.
set -euo pipefail
SSHOPTS=(-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa)
HOST=root@127.0.0.1
REMOTE=$(ssh "${SSHOPTS[@]}" -p 2222 "$HOST" '
  files=$(find /var/mobile/Media/DCIM -type f -iname "*.png" -print)
  if [ -n "$files" ]; then
    printf "%s\n" "$files" | xargs ls -t | head -n 1
  fi
')
if [[ -z "$REMOTE" || ! "$REMOTE" =~ \.[Pp][Nn][Gg]$ ]]; then
  echo 'No PNG screenshot found in /var/mobile/Media/DCIM. Capture with Home+Power first.' >&2
  exit 1
fi
DEST="$HOME/Downloads/Blender3GS-$(date +%Y%m%d-%H%M%S).png"
scp -O "${SSHOPTS[@]}" -P 2222 "$HOST:$REMOTE" "$DEST"
echo "Saved: $DEST"
open "$DEST"