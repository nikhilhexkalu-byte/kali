#!/bin/bash
# /opt/challenges/capt-basic/provision.sh
# CAPT Basic Practical — Beginner pentest lab
#
# Network: 127.20.{SLOT}.0/24 (3 hosts)
#   .10  SecureBlog Web App    (directory listing, default creds, SQLi)
#   .11  FileVault Server      (exposed backup files, credential leaks)
#   .12  CommandCenter          (command injection + SUID privesc → FLAG)
set -euo pipefail

PORT=$((8100 + (CHX_LAB_NUM - 1) * 10))
ROOT="/srv/challenge/${CHX_LAB_USER}"
NET="127.20.${CHX_LAB_NUM}"
CHALLENGE_DIR="$(dirname "$0")"
SVC="web-chx${CHX_LAB_NUM}"

rm -rf "$ROOT"; mkdir -p "$ROOT"

# ── Per-slot service user ─────────────────────────────────────────
useradd -r -s /usr/sbin/nologin "$SVC" 2>/dev/null || true
getent group "$SVC" >/dev/null 2>&1 || groupadd -r "$SVC"
usermod -aG "$SVC" "$SVC" 2>/dev/null || true

# ── Restrict challenge directory ──────────────────────────────────
chown root:"$SVC" "$ROOT"
chmod 750 "$ROOT"

# ── Plant the flag (root-only, needs SUID privesc to read) ────────
install -o root -g root -m 600 /dev/null "$ROOT/flag.txt"
printf '%s\n' "$CHX_FLAG" > "$ROOT/flag.txt"

# ── SUID binary for privilege escalation ──────────────────────────
cp /usr/bin/find "$ROOT/finder"
chown root:"$SVC" "$ROOT/finder"
chmod 4750 "$ROOT/finder"

# ── Copy lab script ───────────────────────────────────────────────
cp "${CHALLENGE_DIR}/lab.py" "$ROOT/lab.py"
chmod 640 "$ROOT/lab.py"
chown root:"$SVC" "$ROOT/lab.py"

# ── Writable dirs for the service user ────────────────────────────
mkdir -p "$ROOT/data"
chown "$SVC":"$SVC" "$ROOT/data"
chmod 700 "$ROOT/data"
touch "$ROOT/data/blog.db"
chown "$SVC":"$SVC" "$ROOT/data/blog.db"
chmod 600 "$ROOT/data/blog.db"

# ── Start the lab ─────────────────────────────────────────────────
LAB_LOG="/tmp/lab-${CHX_LAB_NUM}.log"
SVC_PORT=$PORT

nohup runuser -u "$SVC" -- env \
  CHX_LAB_NUM="$CHX_LAB_NUM" \
  SVC_PORT="$SVC_PORT" \
  python3 "$ROOT/lab.py" > "$LAB_LOG" 2>&1 &
LAB_PID=$!

sleep 2
if ! kill -0 "$LAB_PID" 2>/dev/null; then
  echo "FATAL: lab.py died on startup. Log:" >&2
  cat "$LAB_LOG" >&2
  exit 1
fi

# ── Mission briefing ─────────────────────────────────────────────
cat > "${CHX_LAB_HOME}/README.txt" << EOF
╔══════════════════════════════════════════════════════════════╗
║              CAPT PRACTICAL EXAM                             ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Target Network: ${NET}.10-12                          ║
║  Port Range:     ${SVC_PORT}-$((SVC_PORT + 2))                              ║
║                                                              ║
║  Your objectives:                                            ║
║   1. Scan the target network and discover services           ║
║   2. Identify the web technologies and versions              ║
║   3. Find and exploit vulnerabilities                        ║
║   4. Gather credentials and sensitive data                   ║
║   5. Escalate privileges to capture the flag                 ║
║                                                              ║
║  The flag format is: CHX{...}                                ║
║                                                              ║
║  Hints:                                                      ║
║   - Start with: nmap -sT -p ${SVC_PORT}-$((SVC_PORT + 2)) ${NET}.10-12  ║
║   - Check each service for common misconfigurations          ║
║   - Look for default credentials and exposed files           ║
║   - Information from one host helps attack another           ║
║                                                              ║
║  Tools available: nmap, curl, nikto, sqlmap, gobuster, hydra ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
chown "${CHX_LAB_USER}:${CHX_LAB_USER}" "${CHX_LAB_HOME}/README.txt"

echo "provisioned ${CHX_LAB_USER} — lab network ${NET}.0/24 (3 services on :${SVC_PORT}-$((SVC_PORT + 2)))"
