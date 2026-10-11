#!/bin/bash
# /usr/local/bin/lab-cleanup.sh — Full slot sanitization
# Called when a lease ends or a slot is reclaimed. Ensures no trace
# of the previous student remains: processes, files, tmux, /tmp.
# Usage: lab-cleanup.sh <lab_number>
set -uo pipefail

LAB_NUM="${1:?usage: lab-cleanup.sh <lab_number>}"
LAB_USER="lab${LAB_NUM}"
HOME_DIR="/home/${LAB_USER}"
CLEAN_BASHRC="/etc/cyberhx/clean-bashrc"

# ── Kill all processes owned by the lab user (ensure fully dead) ──
pkill -STOP -u "$LAB_USER" 2>/dev/null || true
pkill -9 -u "$LAB_USER" 2>/dev/null || true
while pgrep -u "$LAB_USER" >/dev/null 2>&1; do
  pkill -9 -u "$LAB_USER" 2>/dev/null || true
  sleep 0.2
done

# ── Kill tmux sessions for this slot ─────────────────────────────
tmux kill-session -t "lab${LAB_NUM}" 2>/dev/null || true

# ── Kill the per-slot web service user ────────────────────────────
pkill -9 -u "www-chx${LAB_NUM}" 2>/dev/null || true

# ── Wipe and atomically recreate the home directory ───────────────
# Removes the entire directory (no symlink following) then recreates
# it with correct ownership. Files are written as the lab user to
# prevent symlink-following attacks.
rm -rf "${HOME_DIR:?}"
install -d -o "${LAB_USER}" -g "${LAB_USER}" -m 700 "${HOME_DIR}"

if [ -f "$CLEAN_BASHRC" ]; then
  runuser -u "${LAB_USER}" -- install -m 644 /dev/stdin "${HOME_DIR}/.bashrc" < "$CLEAN_BASHRC"
else
  runuser -u "${LAB_USER}" -- install -m 644 /dev/stdin "${HOME_DIR}/.bashrc" < /etc/skel/.bashrc
fi
runuser -u "${LAB_USER}" -- install -m 644 /dev/stdin "${HOME_DIR}/.profile" < /etc/skel/.profile

# ── Clean /tmp files owned by the lab user ────────────────────────
find /tmp -maxdepth 2 -user "$LAB_USER" -exec rm -rf {} + 2>/dev/null || true

# ── Clean /srv/challenge for this slot ────────────────────────────
rm -rf "/srv/challenge/${LAB_USER}" 2>/dev/null || true

# ── Remove session markers ────────────────────────────────────────
rm -f "/tmp/.lab-session-${LAB_NUM}" "/tmp/.lab-end-time-${LAB_NUM}" 2>/dev/null || true

echo "[cleanup] Lab ${LAB_NUM}: fully sanitized"
