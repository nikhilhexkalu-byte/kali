#!/bin/bash
# /opt/challenges/capt-day11/provision.sh
# CAPT Day 11: Privilege Escalation
set -euo pipefail

PORT=$((8100 + (CHX_LAB_NUM - 1) * 10))
ROOT="/srv/challenge/${CHX_LAB_USER}"
NET="127.20.${CHX_LAB_NUM}"
CHALLENGE_DIR="$(dirname "$0")"
SVC="web-chx${CHX_LAB_NUM}"

rm -rf "$ROOT"; mkdir -p "$ROOT"

useradd -r -s /usr/sbin/nologin "$SVC" 2>/dev/null || true

# Plant the flag (root-only)
install -o root -g root -m 600 /dev/null "$ROOT/flag.txt"
printf '%s\n' "$CHX_FLAG" > "$ROOT/flag.txt"

# Copy lab script
cp "${CHALLENGE_DIR}/lab.py" "$ROOT/lab.py"
chmod 640 "$ROOT/lab.py"
chown root:"$SVC" "$ROOT/lab.py"


# SUID binary for privilege escalation
cp /usr/bin/find "$ROOT/finder"
chown root:"$SVC" "$ROOT/finder"
chmod 4750 "$ROOT/finder"


# Start the lab
nohup runuser -u "$SVC" -- env \
  CHX_LAB_NUM="$CHX_LAB_NUM" \
  SVC_PORT="$PORT" \
  CHX_FLAG="$CHX_FLAG" \
  python3 "$ROOT/lab.py" > "/tmp/lab-${CHX_LAB_NUM}.log" 2>&1 &
LAB_PID=$!

sleep 2
if ! kill -0 "$LAB_PID" 2>/dev/null; then
  echo "FATAL: lab.py died on startup. Log:" >&2
  cat "/tmp/lab-${CHX_LAB_NUM}.log" >&2
  exit 1
fi

cat > "${CHX_LAB_HOME}/README.txt" << EOF
╔══════════════════════════════════════════════════════════════╗
║              CAPT DAY 11: Privilege Escalation
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Target: http://${NET}.10:${PORT}                          ║
║                                                              ║
║  Find and exploit SUID binaries to read the flag.
║                                                              ║
║  Flag format: CHX{...}                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
chown "${CHX_LAB_USER}:${CHX_LAB_USER}" "${CHX_LAB_HOME}/README.txt"

echo "provisioned ${CHX_LAB_USER} — day11 on ${NET}.10:${PORT}"
