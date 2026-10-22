#!/bin/bash
# Deploy CAPT challenge labs to vm.cyberhx.com
# Run this ON the lab server as root:
#   curl -sL https://raw.githubusercontent.com/nikhilhexkalu-byte/kali/main/deploy-challenges.sh | bash
# Or: ssh into the server and run this script.
set -euo pipefail

CHALLENGE_DIR="/opt/challenges"
REPO="https://github.com/nikhilhexkalu-byte/kali.git"
TMP="/tmp/kali-deploy-$$"

echo "[deploy] Cloning challenge repo..."
git clone --depth 1 "$REPO" "$TMP"

echo "[deploy] Installing 14 CAPT challenges to $CHALLENGE_DIR..."
mkdir -p "$CHALLENGE_DIR"

for day in $(seq -w 1 14); do
  src="$TMP/challenges/capt-day${day}"
  dst="$CHALLENGE_DIR/capt-day${day}"
  if [ ! -d "$src" ]; then
    echo "[deploy] WARNING: $src not found, skipping"
    continue
  fi
  rm -rf "$dst"
  cp -r "$src" "$dst"
  chmod +x "$dst/provision.sh" "$dst/teardown.sh" 2>/dev/null || true
  chmod 644 "$dst/lab.py" 2>/dev/null || true
  echo "[deploy] Installed capt-day${day}"
done

rm -rf "$TMP"

echo "[deploy] Verifying..."
for day in $(seq -w 1 14); do
  if [ -x "$CHALLENGE_DIR/capt-day${day}/provision.sh" ]; then
    echo "  ✓ capt-day${day}"
  else
    echo "  ✗ capt-day${day} MISSING"
  fi
done

echo "[deploy] Done. All 14 CAPT challenges installed."
