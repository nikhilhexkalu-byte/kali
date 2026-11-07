#!/bin/bash
# /opt/challenges/capt-day11/provision.sh
# CAPT Day 11: Privilege Escalation
set -euo pipefail
. /usr/local/lib/chx/chx-slot.sh

PORT=$((8100 + (CHX_LAB_NUM - 1) * 10))
ROOT="/srv/challenge/${CHX_LAB_USER}"
NET="127.20.${CHX_LAB_NUM}"
CHALLENGE_DIR="$(dirname "$0")"
SVC="web-chx${CHX_LAB_NUM}"

rm -rf "$ROOT"; mkdir -p "$ROOT"

useradd -r -s /usr/sbin/nologin "$SVC" 2>/dev/null || true

# Plant the flag (root-only)
# The flag belongs to a per-slot user, never root: every slot shares one container, so a SUID-root
# escalation would hand the learner every other learner's lab and the lab secrets.
FLAGU="flag-chx${CHX_LAB_NUM}"
useradd -r -M -s /usr/sbin/nologin "$FLAGU" 2>/dev/null || true
install -o "$FLAGU" -g "$FLAGU" -m 400 /dev/null "$ROOT/flag.txt"
printf '%s\n' "$CHX_FLAG" > "$ROOT/flag.txt"
# Service-user-only copy for the challenge web application (not in the env)
install -o "$SVC" -g "$SVC" -m 400 /dev/stdin "$ROOT/.flag" <<< "$CHX_FLAG"

# Copy lab script
cp "${CHALLENGE_DIR}/lab.py" "$ROOT/lab.py"
chmod 640 "$ROOT/lab.py"
chown root:"$SVC" "$ROOT/lab.py"


# SUID binary for privilege escalation
cp /usr/bin/find "$ROOT/finder"
chown "$FLAGU":"$SVC" "$ROOT/finder"
chmod 4750 "$ROOT/finder"


# Start the lab
LAB_LOG="$(chx_log_path "$CHX_LAB_NUM")"
# Kill any stale process from a previous session on this slot
pkill -9 -u "$SVC" 2>/dev/null || true
# Wait until the port is free so the new process can bind it
chx_free_block "$(chx_block_base "$CHX_LAB_NUM")"
nohup runuser -u "$SVC" -- env \
  CHX_LAB_NUM="$CHX_LAB_NUM" \
  SVC_PORT="$PORT" \
  CHX_LAB_USER="$CHX_LAB_USER" \
  python3 /usr/local/lib/chx/chx-guard.py "$ROOT/lab.py" > "$LAB_LOG" 2>&1 &
LAB_PID=$!

if ! chx_wait_listen "${SVC_PORT:-$PORT}" "$SVC"; then
  echo "FATAL: lab.py not listening on :${SVC_PORT:-$PORT} (nohup PID=$LAB_PID). Log:" >&2
  cat "$LAB_LOG" >&2
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
