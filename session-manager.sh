#!/bin/bash
# ── Session Manager ──────────────────────────────────────────────
# Runs as a background daemon. Checks session files every 30s
# and kills any that have exceeded the timeout.

SESSION_TIMEOUT="${SESSION_TIMEOUT:-900}"
MAX_LABS="${MAX_LABS:-10}"
CREDS_FILE="/tmp/lab-credentials.json"

echo "[session-mgr] Started — timeout=${SESSION_TIMEOUT}s, labs=${MAX_LABS}"

while true; do
  sleep 30

  NOW=$(date +%s)

  for i in $(seq 1 "$MAX_LABS"); do
    SESSION_FILE="/tmp/.lab-session-${i}"
    LAB_USER="lab${i}"

    if [ -f "$SESSION_FILE" ]; then
      START=$(cat "$SESSION_FILE" 2>/dev/null || echo "0")
      ELAPSED=$((NOW - START))

      if [ "$ELAPSED" -ge "$((SESSION_TIMEOUT + 30))" ]; then
        echo "[session-mgr] Lab ${i}: session expired (${ELAPSED}s) — cleaning up"

        /usr/local/bin/lab-cleanup.sh "$i"

        echo "[session-mgr] Lab ${i}: fully sanitized and ready for next user"
      fi
    fi
  done

  # Update active status in public JSON
  ACTIVE_JSON='{"labs":['
  for i in $(seq 1 "$MAX_LABS"); do
    SESSION_FILE="/tmp/.lab-session-${i}"
    COMMA=""
    [ "$i" -gt 1 ] && COMMA=","

    IS_ACTIVE="false"
    TIME_LEFT=""
    if [ -f "$SESSION_FILE" ]; then
      IS_ACTIVE="true"
      START=$(cat "$SESSION_FILE" 2>/dev/null || echo "$NOW")
      REMAINING=$((SESSION_TIMEOUT - (NOW - START)))
      [ "$REMAINING" -lt 0 ] && REMAINING=0
      TIME_LEFT="\"timeLeft\":${REMAINING},"
    fi

    ACTIVE_JSON="${ACTIVE_JSON}${COMMA}{\"id\":${i},\"user\":\"lab${i}\",\"path\":\"/lab/${i}/\",${TIME_LEFT}\"active\":${IS_ACTIVE}}"
  done
  ACTIVE_JSON="${ACTIVE_JSON}]}"
  echo "$ACTIVE_JSON" > /var/www/landing/labs-public.json

done
