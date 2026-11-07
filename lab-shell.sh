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

# Refuse to start a new shell if the lease has already expired.
# Without this, ttyd (running as root) would immediately spawn a fresh
# bash on reconnect, giving the student an hour of extra time with a
# 00:00 display.
if [ -n "$END_TIME" ] && [ "$END_TIME" -gt 0 ] 2>/dev/null && [ "$END_TIME" -le "$NOW" ] 2>/dev/null; then
  echo -e "\033[1;31m"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  Session expired. Return to the platform to start    ║"
  echo "║  a new lab session.                                  ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "\033[0m"
  sleep 5
  exit 0
fi

if [ -n "$END_TIME" ] && [ "$END_TIME" -gt "$NOW" ] 2>/dev/null; then
  SESSION_TIMEOUT=$((END_TIME - NOW))
else
  SESSION_TIMEOUT="${SESSION_TIMEOUT:-3600}"
fi

WARNING_TIME=$((SESSION_TIMEOUT - 60))
[ "$WARNING_TIME" -lt 5 ] && WARNING_TIME=5

# Record session start (root-only — users can't tamper with timeouts)
echo "$(date +%s)" > "$SESSION_FILE"
chmod 600 "$SESSION_FILE" 2>/dev/null || true

# Capture ttyd PID now (PPID of this script = ttyd) so the background
# subshell can kill it without needing fuser (psmisc not installed).
TTYD_PID=$PPID

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

  # Only end THIS session. If the slot was released and leased to someone else
  # meanwhile, the deadline file is gone or holds the new lease's deadline: a
  # stale countdown must never kill the next learner's shell.
  still_mine() { [ "$(cat "$LAB_END_FILE" 2>/dev/null || echo "")" = "$END_TIME" ]; }
  still_mine || exit 0

  echo ""
  echo -e "\033[1;31m"
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  SESSION EXPIRED — disconnecting in 5s...            ║"
  echo "╚══════════════════════════════════════════════════════╝"
  echo -e "\033[0m"

  sleep 5
  still_mine || exit 0

  # Kill all this slot's processes, then kill ttyd directly by PID.
  # fuser (psmisc) is not installed on the image; kill $TTYD_PID is simpler
  # and more reliable — PPID of this script is always the ttyd process.
  rm -f "$SESSION_FILE"
  pkill -9 -u "$LAB_USER" 2>/dev/null || true
  kill -9 "$TTYD_PID" 2>/dev/null || true
) &
TIMER_PID=$!

# Run interactive shell as the lab user inside tmux so reconnecting
# the browser tab reattaches to the same session (command history,
# running processes, and screen state are preserved).
TMUX_SESSION="lab${LAB_NUM}"
cd "/home/${LAB_USER}"
exec runuser -u "$LAB_USER" -- env \
  HOME="/home/${LAB_USER}" \
  USER="$LAB_USER" \
  LOGNAME="$LAB_USER" \
  SESSION_TIMEOUT="$SESSION_TIMEOUT" \
  LAB_END_TIME="$END_TIME" \
  tmux new-session -A -s "$TMUX_SESSION"
