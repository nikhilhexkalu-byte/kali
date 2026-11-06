#!/bin/bash
# /opt/challenges/capt-day01/provision.sh
# CAPT Day 01: Reconnaissance
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
# Service-user-only copy for the challenge web application (not in the env)
install -o "$SVC" -g "$SVC" -m 400 /dev/stdin "$ROOT/.flag" <<< "$CHX_FLAG"

# Copy lab script
cp "${CHALLENGE_DIR}/lab.py" "$ROOT/lab.py"
chmod 640 "$ROOT/lab.py"
chown root:"$SVC" "$ROOT/lab.py"



# Start the lab
# Kill any stale process from a previous session on this slot
pkill -u "$SVC" 2>/dev/null || true
sleep 0.5
nohup runuser -u "$SVC" -- env \
  CHX_LAB_NUM="$CHX_LAB_NUM" \
  SVC_PORT="$PORT" \
  python3 "$ROOT/lab.py" > "/tmp/lab-${CHX_LAB_NUM}.log" 2>&1 &
LAB_PID=$!

sleep 2
if ! ss -tln 2>/dev/null | grep -q ":${PORT}"; then
  echo "FATAL: lab.py not listening on :${PORT} (nohup PID=$LAB_PID). Log:" >&2
  cat "/tmp/lab-${CHX_LAB_NUM}.log" >&2
  exit 1
fi

cat > "${CHX_LAB_HOME}/README.txt" << EOF
╔══════════════════════════════════════════════════════════════╗
║              CAPT DAY 01: Reconnaissance
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Target: http://${NET}.10:${PORT}                          ║
║                                                              ║
║  Use nmap and web enumeration to discover hidden paths.
║                                                              ║
║  Flag format: CHX{...}                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
chown "${CHX_LAB_USER}:${CHX_LAB_USER}" "${CHX_LAB_HOME}/README.txt"

echo "provisioned ${CHX_LAB_USER} — day01 on ${NET}.10:${PORT}"
