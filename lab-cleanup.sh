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

# ── Kill the slot's root-owned helpers first ─────────────────────
# lab-shell.sh leaves a root countdown subshell per connection, and runuser (root)
# is the parent of the learner's shell. A leftover countdown from the previous
# learner would later kill the NEXT learner's session, so it must go now.
pkill -9 -f "^/bin/bash /usr/local/bin/lab-shell.sh ${LAB_NUM}\$" 2>/dev/null || true
pkill -9 -f "^runuser -u ${LAB_USER} -- " 2>/dev/null || true

# ── Kill everything the lab user, the slot's service user and its flag user run ──
# No SIGSTOP first: stopping the learner's processes also stopped their root
# parent (runuser stops itself when its child stops), the killed children then
# stayed zombies nobody reaped, pgrep kept matching them and this loop never ended
# (the 30 s "cleanup timed out" in the logs). Zombies are ignored and the loop is
# bounded.
alive() {
  local u
  for u in "$LAB_USER" "web-chx${LAB_NUM}" "www-chx${LAB_NUM}" "flag-chx${LAB_NUM}"; do
    id -u "$u" >/dev/null 2>&1 || continue
    ps -o stat= -u "$u" 2>/dev/null | grep -qv '^Z' && return 0
  done
  return 1
}
for _ in $(seq 1 25); do
  for u in "$LAB_USER" "web-chx${LAB_NUM}" "www-chx${LAB_NUM}" "flag-chx${LAB_NUM}"; do
    pkill -9 -u "$u" 2>/dev/null || true
  done
  alive || break
  sleep 0.2
done
alive && echo "[cleanup] Lab ${LAB_NUM}: WARNING some processes survived" >&2

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
# Suppress the Kali minimal-install MOTD ("Message from Kali developers")
touch "${HOME_DIR}/.hushlogin"
chown "${LAB_USER}:${LAB_USER}" "${HOME_DIR}/.hushlogin" 2>/dev/null || true

# ── Clean /tmp files owned by the lab user ────────────────────────
find /tmp -maxdepth 2 -user "$LAB_USER" -exec rm -rf {} + 2>/dev/null || true

# ── Clean /srv/challenge for this slot ────────────────────────────
rm -rf "/srv/challenge/${LAB_USER}" 2>/dev/null || true

# ── Remove session markers ────────────────────────────────────────
rm -f "/tmp/.lab-session-${LAB_NUM}" "/tmp/.lab-end-time-${LAB_NUM}" 2>/dev/null || true
# Old world-readable service log (services now log to /var/log/chx, root only)
rm -f "/tmp/lab-${LAB_NUM}.log" 2>/dev/null || true

echo "[cleanup] Lab ${LAB_NUM}: fully sanitized"
