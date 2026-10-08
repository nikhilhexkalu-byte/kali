#!/bin/bash
set -e

USER_NAME="${TERMINAL_USER:-kali}"

# If no password is configured, generate a random one and print it to the
# service logs (Render dashboard -> Logs) instead of crashing.
if [ -z "$TERMINAL_PASSWORD" ]; then
  TERMINAL_PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)"
  echo "=============================================================="
  echo "TERMINAL_PASSWORD env var not set - generated a temporary one:"
  echo "  user:     ${USER_NAME}"
  echo "  password: ${TERMINAL_PASSWORD}"
  echo "Set TERMINAL_PASSWORD in Render > Environment to make it permanent."
  echo "=============================================================="
fi

PORT="${PORT:-10000}"
echo "Starting web terminal on port ${PORT} as user '${USER_NAME}'"

# Web terminal on the port Render provides, protected by basic auth.
# -W writable, -m max simultaneous clients, -t client options.
#
# The terminal runs as the normal user "student" (not root). Use `sudo` when
# a tool needs root privileges.
cd /home/student
exec runuser -u student -- env HOME=/home/student USER=student LOGNAME=student \
  ttyd -W -p "${PORT}" -m 5 \
  -c "${USER_NAME}:${TERMINAL_PASSWORD}" \
  -t fontSize=15 -t disableLeaveAlert=true \
  tmux new -A -s main bash
