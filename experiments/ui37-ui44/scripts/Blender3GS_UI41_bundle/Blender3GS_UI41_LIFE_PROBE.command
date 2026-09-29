#!/bin/bash
set -euo pipefail
# Requires an existing iproxy 2222:22 tunnel; read-only monitoring.
echo 'Open Blender first. Press Home after first sample. Do not reopen it.'
for delay in 0 2 10 30; do
  if (( delay > 0 )); then sleep "$delay"; fi
  echo "=== Blender PID after +${delay}s ==="
  ssh -o ConnectTimeout=5 -o HostKeyAlgorithms=+ssh-rsa \
      -o PubkeyAcceptedAlgorithms=+ssh-rsa -p 2222 root@127.0.0.1 \
      "date; ps -A | grep '[B]lender3GS' || echo NOT_RUNNING" || true
done
