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

# ── Kill all processes owned by the lab user ──────────────────────
pkill -9 -u "$LAB_USER" 2>/dev/null || true

# ── Kill tmux sessions for this slot ─────────────────────────────
tmux kill-session -t "lab${LAB_NUM}" 2>/dev/null || true

# ── Kill the per-slot web service user ────────────────────────────
pkill -9 -u "www-chx${LAB_NUM}" 2>/dev/null || true

# ── Wipe the home directory completely and restore clean state ────
rm -rf "${HOME_DIR:?}"/.[!.]* "${HOME_DIR:?}"/..?* "${HOME_DIR:?}"/* 2>/dev/null || true

if [ -f "$CLEAN_BASHRC" ]; then
  cp "$CLEAN_BASHRC" "${HOME_DIR}/.bashrc"
else
  cp /etc/skel/.bashrc "${HOME_DIR}/.bashrc" 2>/dev/null || true
fi
cp /etc/skel/.profile "${HOME_DIR}/.profile" 2>/dev/null || true

chown "${LAB_USER}:${LAB_USER}" "${HOME_DIR}/.bashrc" "${HOME_DIR}/.profile" 2>/dev/null || true
chmod 700 "$HOME_DIR"

# ── Clean /tmp files owned by the lab user ────────────────────────
find /tmp -maxdepth 2 -user "$LAB_USER" -exec rm -rf {} + 2>/dev/null || true

# ── Clean /srv/challenge for this slot ────────────────────────────
rm -rf "/srv/challenge/${LAB_USER}" 2>/dev/null || true

# ── Remove session markers ────────────────────────────────────────
rm -f "/tmp/.lab-session-${LAB_NUM}" "/tmp/.lab-end-time-${LAB_NUM}" 2>/dev/null || true

echo "[cleanup] Lab ${LAB_NUM}: fully sanitized"
