#!/bin/bash
# ── Lab Shell Wrapper ────────────────────────────────────────────
# Launched by ttyd for each user. Syncs countdown with stage timer
# when /tmp/.stage-end-time exists (exam mode), else uses SESSION_TIMEOUT.
# Usage: lab-shell.sh <lab_number>

LAB_NUM="${1:-1}"
LAB_USER="lab${LAB_NUM}"
SESSION_FILE="/tmp/.lab-session-${LAB_NUM}"
LAB_END_FILE="/tmp/.lab-end-time-${LAB_NUM}"
STAGE_END_FILE="/tmp/.stage-end-time"

# ── Calculate remaining time ─────────────────────────────────────
# Prefer this lab's own deadline (written per lease or per demo stage). The
# shared stage file is only a fallback for older callers; a leased session
# must never inherit a stale stage clock.
NOW=$(date +%s)
END_TIME=""
if [ -f "$LAB_END_FILE" ]; then
  END_TIME=$(cat "$LAB_END_FILE" 2>/dev/null || echo "")
elif [ -f "$STAGE_END_FILE" ]; then
  END_TIME=$(cat "$STAGE_END_FILE" 2>/dev/null || echo "")
fi

if [ -n "$END_TIME" ] && [ "$END_TIME" -gt "$NOW" ] 2>/dev/null; then
  SESSION_TIMEOUT=$((END_TIME - NOW))
else
  SESSION_TIMEOUT="${SESSION_TIMEOUT:-900}"
fi

WARNING_TIME=$((SESSION_TIMEOUT - 60))
[ "$WARNING_TIME" -lt 5 ] && WARNING_TIME=5

# Record session start (root-only — users can't tamper with timeouts)
echo "$(date +%s)" > "$SESSION_FILE"
chmod 600 "$SESSION_FILE" 2>/dev/null || true

# Background countdown — warns at T-60s, kills at T-0
(
  sleep "$WARNING_TIME" 2>/dev/null

  # 60-second warning
  echo ""
  echo -e "\033[1;33m"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  WARNING: Session expires in 60 seconds!             ║"
  echo "║  Save your work. A new session will be available.   ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "\033[0m"

  sleep 55 2>/dev/null

  echo ""
  echo -e "\033[1;31m"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  SESSION EXPIRED — disconnecting in 5s...            ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "\033[0m"

  sleep 5

  # Kill only this lab user's processes
  rm -f "$SESSION_FILE"
  pkill -9 -u "$LAB_USER" 2>/dev/null || true
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
