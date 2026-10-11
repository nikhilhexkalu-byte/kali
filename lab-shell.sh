#!/bin/bash
# ── Lab Shell Wrapper ────────────────────────────────────────────
# Launched by ttyd for each user. Enforces the 15-minute timeout.
# Usage: lab-shell.sh <lab_number>

LAB_NUM="${1:-1}"
LAB_USER="lab${LAB_NUM}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-900}"
SESSION_FILE="/tmp/.lab-session-${LAB_NUM}"
WARNING_TIME=$((SESSION_TIMEOUT - 60))

# Record session start
echo "$(date +%s)" > "$SESSION_FILE"
chmod 666 "$SESSION_FILE" 2>/dev/null || true

# Background countdown — warns at T-60s, kills at T-0
(
  sleep "$WARNING_TIME" 2>/dev/null

  # 60-second warning
  echo ""
  echo -e "\033[1;33m"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  ⚠  WARNING: Session expires in 60 seconds!         ║"
  echo "║  Save your work. A new session will be available.   ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "\033[0m"

  sleep 55 2>/dev/null

  echo ""
  echo -e "\033[1;31m"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  🔴  Session expired — disconnecting in 5s...        ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "\033[0m"

  sleep 5

  # Kill all processes for this user
  rm -f "$SESSION_FILE"
  pkill -u "$LAB_USER" 2>/dev/null
  kill -9 -1 2>/dev/null
) &
TIMER_PID=$!

# Run interactive shell as the lab user
cd "/home/${LAB_USER}"
exec runuser -u "$LAB_USER" -- env \
  HOME="/home/${LAB_USER}" \
  USER="$LAB_USER" \
  LOGNAME="$LAB_USER" \
  SESSION_TIMEOUT="$SESSION_TIMEOUT" \
  bash --login
