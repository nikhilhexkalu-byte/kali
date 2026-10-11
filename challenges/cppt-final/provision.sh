#!/bin/bash
# /opt/challenges/cppt-final/provision.sh
# CPPT Final Practical — Multi-service pentest lab
#
# Network: 127.10.{SLOT}.0/24 (5 hosts)
#   .10  Corporate Web Portal   (SQLi on login)
#   .11  File Server            (directory listing + credential leak)
#   .12  Database Admin Panel   (default creds → data exposure)
#   .13  Internal REST API      (IDOR + unauthenticated config)
#   .14  Admin Dashboard        (command injection + SUID privesc → FLAG)
set -euo pipefail

PORT=$((8000 + CHX_LAB_NUM))
ROOT="/srv/challenge/${CHX_LAB_USER}"
NET="127.10.${CHX_LAB_NUM}"
CHALLENGE_DIR="$(dirname "$0")"

rm -rf "$ROOT"; mkdir -p "$ROOT"

# ── Per-slot service user ─────────────────────────────────────────
useradd -r -s /usr/sbin/nologin "www-chx${CHX_LAB_NUM}" 2>/dev/null || true
usermod -aG "${CHX_LAB_USER}" "www-chx${CHX_LAB_NUM}" 2>/dev/null || true

# ── Restrict challenge directory ──────────────────────────────────
chown root:"${CHX_LAB_USER}" "$ROOT"
chmod 750 "$ROOT"

# ── Plant the flag (root-only, needs SUID privesc to read) ────────
install -o root -g root -m 600 /dev/null "$ROOT/flag.txt"
printf '%s\n' "$CHX_FLAG" > "$ROOT/flag.txt"

# ── SUID binary for privilege escalation (per-slot isolated) ──────
cp /usr/bin/find "$ROOT/finder"
chown root:"${CHX_LAB_USER}" "$ROOT/finder"
chmod 4750 "$ROOT/finder"

# ── Copy lab network script ───────────────────────────────────────
cp "${CHALLENGE_DIR}/lab.py" "$ROOT/lab.py"
chmod 640 "$ROOT/lab.py"
chown root:"${CHX_LAB_USER}" "$ROOT/lab.py"

# ── Start the lab network as the per-slot service user ────────────
CHX_LAB_NUM=$CHX_LAB_NUM CHX_FLAG="$CHX_FLAG" \
  nohup python3 "$ROOT/lab.py" > /dev/null 2>&1 &

# ── Drop the mission brief in the lab user's home ─────────────────
cat > "${CHX_LAB_HOME}/README.txt" << EOF
╔══════════════════════════════════════════════════════════════╗
║              CPPT FINAL PRACTICAL EXAM                       ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Target Network: ${NET}.0/24                           ║
║                                                              ║
║  Your objectives:                                            ║
║   1. Enumerate the target network and discover services      ║
║   2. Identify vulnerabilities on each host                   ║
║   3. Exploit them to gather evidence                         ║
║   4. Escalate privileges to capture the flag                 ║
║                                                              ║
║  The flag format is: CHX{...}                                ║
║                                                              ║
║  You will be asked questions about:                          ║
║   - Vulnerability types found                                ║
║   - Software versions discovered                             ║
║   - Credentials obtained                                     ║
║   - Number of records exposed                                ║
║                                                              ║
║  Tools: nmap -sT, curl, sqlmap, nikto, gobuster             ║
║  Time:  60 minutes from launch                               ║
║                                                              ║
║  Start with: nmap -sT ${NET}.0/24                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
chown "${CHX_LAB_USER}:${CHX_LAB_USER}" "${CHX_LAB_HOME}/README.txt"

echo "provisioned ${CHX_LAB_USER} — lab network ${NET}.0/24 (5 services)"
