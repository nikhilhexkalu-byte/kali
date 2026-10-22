#!/bin/bash
set -e

# ── Config ───────────────────────────────────────────────────────
PORT="${PORT:-10000}"
MAX_LABS="${MAX_LABS:-6}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-3600}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ALLOWED_DOMAIN="${ALLOWED_DOMAIN:-cyberhx.com}"
CREDS_FILE="/tmp/lab-credentials.json"
# Shared secret the exam site signs lease requests with. Unset = lease API off.
LEASE_SECRET="${LEASE_SECRET:-}"
# Who may embed the terminal in an iframe. Default: same origin only.
ALLOWED_FRAME_ANCESTORS="${ALLOWED_FRAME_ANCESTORS:-'self'}"
# Whether anonymous visitors can start the local demo exam.
PUBLIC_DEMO="${PUBLIC_DEMO:-false}"
export PUBLIC_DEMO

echo "╔══════════════════════════════════════════════════════════╗"
echo "║        CyberHX Pentest Exam — Starting Up               ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Port       : ${PORT}"
echo "║  Max labs   : ${MAX_LABS}"
echo "║  Timeout    : $((SESSION_TIMEOUT / 60)) min per stage"
echo "║  Stages     : 3 (2 labs each)"
echo "║  Allowed    : *.${ALLOWED_DOMAIN}"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Generate admin password if not set ───────────────────────────
if [ -z "$ADMIN_PASSWORD" ]; then
  ADMIN_PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
  echo ""
  echo "[!] ADMIN_PASSWORD not set — generated one."
  echo "   Set ADMIN_PASSWORD env var in Render to make it permanent."
  echo "   View credentials at: https://<host>/admin"
  echo ""
fi

# Save admin password to root-only file
echo "$ADMIN_PASSWORD" > /tmp/.admin-password
chmod 600 /tmp/.admin-password

# Generate internal API token (for nginx -> exam-api auth)
INTERNAL_TOKEN="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
echo "$INTERNAL_TOKEN" > /tmp/.api-token
chmod 600 /tmp/.api-token
export INTERNAL_TOKEN

# ── Lease API shared secret ──────────────────────────────────────
# Must match LAB_LEASE_SECRET on pentestlab.cyberhx.com. Without it the
# /api/v1 lease API stays disabled and the site cannot start labs.
if [ -n "$LEASE_SECRET" ]; then
  printf '%s' "$LEASE_SECRET" > /tmp/.lease-secret
  chmod 600 /tmp/.lease-secret
  echo "[+] Lease API enabled (LEASE_SECRET set)"
else
  rm -f /tmp/.lease-secret
  echo "[!] LEASE_SECRET not set — /api/v1 lease API DISABLED."
  echo "    The exam site cannot start labs until you set it in Render."
fi

# ── Generate per-lab credentials ─────────────────────────────────
touch "$CREDS_FILE"
chmod 600 "$CREDS_FILE"
echo '{"labs":[' > "$CREDS_FILE"
echo ""
echo "┌──────┬──────────┬────────────────────────┬──────────────┐"
echo "│ Lab  │ User     │ Password               │ Path         │"
echo "├──────┼──────────┼────────────────────────┼──────────────┤"

for i in $(seq 1 "$MAX_LABS"); do
  ENV_VAR="LAB_${i}_PASSWORD"
  PASSWORD="${!ENV_VAR:-}"
  if [ -z "$PASSWORD" ]; then
    PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)"
  fi

  MASKED_PW="${PASSWORD:0:4}************"
  printf "│ %-4s │ %-8s │ %-22s │ %-12s │\n" "$i" "lab${i}" "$MASKED_PW" "/lab/${i}/"

  COMMA=""
  [ "$i" -gt 1 ] && COMMA=","
  echo "${COMMA}{\"id\":${i},\"user\":\"lab${i}\",\"password\":\"${PASSWORD}\",\"path\":\"/lab/${i}/\",\"port\":$((7680 + i)),\"active\":false}" >> "$CREDS_FILE"
done

echo "└──────┴──────────┴────────────────────────┴──────────────┘"
echo ""
echo ']}' >> "$CREDS_FILE"

# ── Write admin password for nginx auth ──────────────────────────
echo "admin:$(echo -n "$ADMIN_PASSWORD" | openssl passwd -apr1 -stdin)" > /etc/nginx/.htpasswd_admin
chown root:www-data /etc/nginx/.htpasswd_admin
chmod 640 /etc/nginx/.htpasswd_admin

# ── Setup network sandbox (try iptables, fallback to proxy-only) ─
echo "[*] Setting up network sandbox..."

IPTABLES_OK=false
if command -v iptables &>/dev/null; then
  ALLOWED_IPS=$(dig +short "$ALLOWED_DOMAIN" "*.${ALLOWED_DOMAIN}" 2>/dev/null | grep -E '^[0-9]' || true)

  if iptables -L -n &>/dev/null 2>&1; then
    IPTABLES_OK=true
    echo "[+] iptables available — setting up firewall rules"

    iptables -A OUTPUT -o lo -j ACCEPT
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    iptables -A OUTPUT -p udp --dport 53 -m owner --uid-owner root -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -m owner --uid-owner root -j ACCEPT

    for ip in $ALLOWED_IPS; do
      iptables -A OUTPUT -d "$ip" -p tcp --dport 443 -j ACCEPT
      iptables -A OUTPUT -d "$ip" -p tcp --dport 80 -j ACCEPT
    done

    iptables -A OUTPUT -p tcp --dport 443 -m owner --uid-owner root -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 80 -m owner --uid-owner root -j ACCEPT

    for i in $(seq 1 "$MAX_LABS"); do
      uid=$(id -u "lab${i}" 2>/dev/null || true)
      if [ -n "$uid" ]; then
        # Block infrastructure ports BEFORE allowing general localhost
        iptables -A OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.0/8 -p tcp --dport 9090 -j DROP
        iptables -A OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.0/8 -p tcp --dport 10000 -j DROP
        # Block other slots' challenge ports (each slot uses 8000+lab_num)
        for j in $(seq 1 "$MAX_LABS"); do
          if [ "$j" -ne "$i" ]; then
            iptables -A OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.0/8 -p tcp --dport $((8000 + j)) -j DROP
          fi
        done
        iptables -A OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.0/8 -j ACCEPT
        iptables -A OUTPUT -m owner --uid-owner "$uid" -j DROP
      fi
    done

    echo "[+] Firewall rules applied — lab users locked to own slot, infra ports blocked"
  fi
fi

if [ "$IPTABLES_OK" = "false" ]; then
  echo "[!] iptables unavailable (container lacks NET_ADMIN)"
  echo "    Using proxy-only filtering (HTTP/HTTPS restricted to *.${ALLOWED_DOMAIN})"
fi

# ── Update tinyproxy filter with allowed domain ──────────────────
echo "\.${ALLOWED_DOMAIN}$" > /etc/tinyproxy/filter.txt
echo "[+] Proxy whitelist: *.${ALLOWED_DOMAIN}"
chmod 600 /etc/tinyproxy/filter.txt

# ── Start tinyproxy ──────────────────────────────────────────────
echo "[*] Starting tinyproxy (filtering proxy on :8888)..."
tinyproxy -c /etc/tinyproxy/tinyproxy.conf
sleep 1

# ── Build nginx config from template ────────────────────────────
echo "[*] Generating nginx config..."

LOCATIONS_TMP="/tmp/nginx-locations.conf"
> "$LOCATIONS_TMP"

for i in $(seq 1 "$MAX_LABS"); do
  INTERNAL_PORT=$((7680 + i))
  cat >> "$LOCATIONS_TMP" <<LOCEOF
    # Terminal ${i}
    location /term/${i}/ {
        proxy_pass http://127.0.0.1:${INTERNAL_PORT}/term/${i}/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

LOCEOF
done

# The demo walkthrough consumes real lab capacity, so unless PUBLIC_DEMO=true
# it sits behind the same basic auth as the admin panel. The X-CHX-Admin header
# is what lab-api trusts, and nginx sets it only on authenticated routes.
if [ "$(printf '%s' "$PUBLIC_DEMO" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
  DEMO_AUTH='# PUBLIC_DEMO=true — anyone may start the walkthrough'
  DEMO_ADMIN_FLAG=''
  echo "[!] PUBLIC_DEMO=true — anonymous visitors can start the demo and use lab capacity"
else
  DEMO_AUTH='auth_basic "CyberHX Admin"; auth_basic_user_file /etc/nginx/.htpasswd_admin;'
  DEMO_ADMIN_FLAG='1'
  echo "[+] Demo walkthrough requires admin login"
fi

# X-Frame-Options has no multi-origin form, so it is only emitted when
# framing stays same-origin. Otherwise CSP frame-ancestors governs alone.
if [ "$ALLOWED_FRAME_ANCESTORS" = "'self'" ]; then
  XFO_HEADER='add_header X-Frame-Options "SAMEORIGIN" always;'
else
  XFO_HEADER='# X-Frame-Options omitted: CSP frame-ancestors allows extra origins'
  echo "[+] Terminal embedding allowed from: ${ALLOWED_FRAME_ANCESTORS}"
fi

sed -e "s|__PORT__|${PORT}|g" \
    -e "s|__INTERNAL_TOKEN__|${INTERNAL_TOKEN}|g" \
    -e "s|__CSP_FRAME_ANCESTORS__|${ALLOWED_FRAME_ANCESTORS}|g" \
    -e "s|__XFO_HEADER__|${XFO_HEADER}|g" \
    -e "s|__DEMO_AUTH__|${DEMO_AUTH}|g" \
    -e "s|__DEMO_ADMIN_FLAG__|${DEMO_ADMIN_FLAG}|g" \
    /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

sed -i "/# __LOCATIONS__/r ${LOCATIONS_TMP}" /etc/nginx/nginx.conf
sed -i '/# __LOCATIONS__/d' /etc/nginx/nginx.conf

rm -f "$LOCATIONS_TMP"
unset INTERNAL_TOKEN  # no longer needed — baked into nginx.conf, on disk at /tmp/.api-token
echo "[+] Nginx config generated (${MAX_LABS} terminal locations)"
chmod 600 /etc/nginx/nginx.conf

# ── Lock down directories from lab users ─────────────────────────
# nginx dir — only root + www-data (nginx worker) can enter
chown root:www-data /etc/nginx
chmod 750 /etc/nginx
# web root — public via nginx, but no direct file reads from terminal
chown -R root:www-data /var/www/landing
chmod -R o-rwx /var/www/landing
# tinyproxy config dir
chmod 750 /etc/tinyproxy
echo "[+] Filesystem locked — lab users cannot read configs or web root"

# ── Start nginx ──────────────────────────────────────────────────
echo "[*] Starting nginx on port ${PORT}..."
nginx
sleep 1

# ── Hide process list from lab users ─────────────────────────────
mount -o remount,hidepid=2 /proc 2>/dev/null && \
  echo "[+] /proc hidden — lab users cannot see other processes" || \
  echo "[!] hidepid=2 unavailable — ps aux may expose credentials"

# ── Start exam API server ────────────────────────────────────────
echo "[*] Starting exam API on :9090..."
python3 /exam-api.py &
EXAM_API_PID=$!
sleep 1

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     CyberHX Exam System is LIVE on port ${PORT}           ║"
echo "║                                                        ║"
echo "║  Exam Page : https://<host>/                           ║"
echo "║  Admin     : https://<host>/admin  (pw in Render env)  ║"
echo "║  Reset     : POST /api/exam/reset  (admin auth)       ║"
echo "║                                                        ║"
echo "║  Stages:                                               ║"
echo "║    1. Reconnaissance  → Labs 1-2  (${SESSION_TIMEOUT}s)        ║"
echo "║    2. Exploitation    → Labs 3-4  (${SESSION_TIMEOUT}s)        ║"
echo "║    3. Post-Exploit    → Labs 5-6  (${SESSION_TIMEOUT}s)        ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Keep container alive — restart exam API if it crashes ────────
cleanup() {
  echo "[!] Shutting down..."
  kill "$EXAM_API_PID" 2>/dev/null
  for i in $(seq 1 "$MAX_LABS"); do
    pkill -u "lab${i}" 2>/dev/null || true
  done
  nginx -s stop 2>/dev/null || true
  kill "$(cat /var/run/tinyproxy/tinyproxy.pid 2>/dev/null)" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Watchdog: restart crashed exam API
while true; do
  sleep 30
  if ! kill -0 "$EXAM_API_PID" 2>/dev/null; then
    echo "[watchdog] Restarting exam API..."
    python3 /exam-api.py &
    EXAM_API_PID=$!
  fi
done
