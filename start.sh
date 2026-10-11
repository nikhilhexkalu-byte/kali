#!/bin/bash
set -e

# ── Config ───────────────────────────────────────────────────────
PORT="${PORT:-10000}"
MAX_LABS="${MAX_LABS:-4}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-900}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
ALLOWED_DOMAIN="${ALLOWED_DOMAIN:-cyberhx.com}"
CREDS_FILE="/tmp/lab-credentials.json"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          CyberHX Pentest Lab — Starting Up              ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Port       : ${PORT}"
echo "║  Max labs   : ${MAX_LABS}"
echo "║  Timeout    : $((SESSION_TIMEOUT / 60)) minutes"
echo "║  Allowed    : *.${ALLOWED_DOMAIN}"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Generate admin password if not set ───────────────────────────
if [ -z "$ADMIN_PASSWORD" ]; then
  ADMIN_PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
  echo ""
  echo "⚠  ADMIN_PASSWORD not set — generated one."
  echo "   Set ADMIN_PASSWORD env var in Render to make it permanent."
  echo "   View credentials at: https://<host>/admin"
  echo ""
fi

# Save admin password to root-only file (accessible via Render shell, not in logs)
echo "$ADMIN_PASSWORD" > /tmp/.admin-password
chmod 600 /tmp/.admin-password

# ── Generate per-lab credentials ─────────────────────────────────
# Create creds file with restricted permissions (root-only)
touch "$CREDS_FILE"
chmod 600 "$CREDS_FILE"
echo '{"labs":[' > "$CREDS_FILE"
echo ""
echo "┌──────┬──────────┬────────────────────────┬──────────────┐"
echo "│ Lab  │ User     │ Password               │ Path         │"
echo "├──────┼──────────┼────────────────────────┼──────────────┤"

for i in $(seq 1 "$MAX_LABS"); do
  # Use env var LAB_N_PASSWORD if set, otherwise generate random
  ENV_VAR="LAB_${i}_PASSWORD"
  PASSWORD="${!ENV_VAR:-}"
  if [ -z "$PASSWORD" ]; then
    PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)"
  fi

  MASKED_PW="${PASSWORD:0:4}************"
  printf "│ %-4s │ %-8s │ %-22s │ %-12s │\n" "$i" "lab${i}" "$MASKED_PW" "/lab/${i}/"

  # Write to creds file
  COMMA=""
  [ "$i" -gt 1 ] && COMMA=","
  echo "${COMMA}{\"id\":${i},\"user\":\"lab${i}\",\"password\":\"${PASSWORD}\",\"path\":\"/lab/${i}/\",\"port\":$((7680 + i)),\"active\":false}" >> "$CREDS_FILE"
done

echo "└──────┴──────────┴────────────────────────┴──────────────┘"
echo ""
echo ']}' >> "$CREDS_FILE"

# ── Write admin password for nginx auth ──────────────────────────
echo "admin:$(echo -n "$ADMIN_PASSWORD" | openssl passwd -apr1 -stdin)" > /etc/nginx/.htpasswd_admin

# ── Setup network sandbox (try iptables, fallback to proxy-only) ─
echo "[*] Setting up network sandbox..."

IPTABLES_OK=false
if command -v iptables &>/dev/null; then
  # Resolve the allowed domain
  ALLOWED_IPS=$(dig +short "$ALLOWED_DOMAIN" "*.${ALLOWED_DOMAIN}" 2>/dev/null | grep -E '^[0-9]' || true)

  if iptables -L -n &>/dev/null 2>&1; then
    IPTABLES_OK=true
    echo "[+] iptables available — setting up firewall rules"

    # Allow loopback
    iptables -A OUTPUT -o lo -j ACCEPT
    iptables -A INPUT -i lo -j ACCEPT

    # Allow established connections
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

    # Allow DNS (needed for tinyproxy)
    iptables -A OUTPUT -p udp --dport 53 -m owner --uid-owner root -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -m owner --uid-owner root -j ACCEPT

    # Allow tinyproxy (runs as root/tinyproxy) to reach allowed domain
    for ip in $ALLOWED_IPS; do
      iptables -A OUTPUT -d "$ip" -p tcp --dport 443 -j ACCEPT
      iptables -A OUTPUT -d "$ip" -p tcp --dport 80 -j ACCEPT
    done

    # Allow tinyproxy user outbound to allowed domain
    iptables -A OUTPUT -p tcp --dport 443 -m owner --uid-owner root -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 80 -m owner --uid-owner root -j ACCEPT

    # Block lab users from direct outbound (force through proxy)
    for i in $(seq 1 "$MAX_LABS"); do
      uid=$(id -u "lab${i}" 2>/dev/null || true)
      if [ -n "$uid" ]; then
        # Allow to loopback (for proxy)
        iptables -A OUTPUT -m owner --uid-owner "$uid" -d 127.0.0.0/8 -j ACCEPT
        # Block everything else
        iptables -A OUTPUT -m owner --uid-owner "$uid" -j DROP
      fi
    done

    echo "[+] Firewall rules applied — lab users forced through proxy"
  fi
fi

if [ "$IPTABLES_OK" = "false" ]; then
  echo "[!] iptables unavailable (container lacks NET_ADMIN)"
  echo "    Using proxy-only filtering (HTTP/HTTPS restricted to *.${ALLOWED_DOMAIN})"
  echo "    Direct TCP connections will NOT be blocked"
fi

# ── Update tinyproxy filter with allowed domain ──────────────────
echo "\.${ALLOWED_DOMAIN}$" > /etc/tinyproxy/filter.txt
echo "[+] Proxy whitelist: *.${ALLOWED_DOMAIN}"

# ── Start tinyproxy ──────────────────────────────────────────────
echo "[*] Starting tinyproxy (filtering proxy on :8888)..."
tinyproxy -c /etc/tinyproxy/tinyproxy.conf
sleep 1

# ── Build nginx config from template ────────────────────────────
echo "[*] Generating nginx config..."

# Write location blocks to a temp file (avoids sed multi-line issues)
LOCATIONS_TMP="/tmp/nginx-locations.conf"
> "$LOCATIONS_TMP"

for i in $(seq 1 "$MAX_LABS"); do
  INTERNAL_PORT=$((7680 + i))
  cat >> "$LOCATIONS_TMP" <<LOCEOF
    # Lab ${i}
    location /lab/${i}/ {
        proxy_pass http://127.0.0.1:${INTERNAL_PORT}/lab/${i}/;
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

# Simple replacements first, then insert location blocks via sed 'r'
sed -e "s|__PORT__|${PORT}|g" \
    /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Replace the marker line with the locations file content
sed -i "/# __LOCATIONS__/r ${LOCATIONS_TMP}" /etc/nginx/nginx.conf
sed -i '/# __LOCATIONS__/d' /etc/nginx/nginx.conf

rm -f "$LOCATIONS_TMP"
echo "[+] Nginx config generated"

# ── Write credentials JSON for landing page ──────────────────────
# Sanitized version (no passwords) for public landing page
echo '{"labs":[' > /var/www/landing/labs-public.json
for i in $(seq 1 "$MAX_LABS"); do
  COMMA=""
  [ "$i" -gt 1 ] && COMMA=","
  echo "${COMMA}{\"id\":${i},\"user\":\"lab${i}\",\"path\":\"/lab/${i}/\"}" >> /var/www/landing/labs-public.json
done
echo ']}' >> /var/www/landing/labs-public.json

# Full credentials for admin endpoint
cp "$CREDS_FILE" /var/www/landing/labs-admin.json

# ── Start nginx ──────────────────────────────────────────────────
echo "[*] Starting nginx on port ${PORT}..."
nginx
sleep 1

# ── Start ttyd instances ─────────────────────────────────────────
echo "[*] Starting ${MAX_LABS} ttyd instances..."

for i in $(seq 1 "$MAX_LABS"); do
  INTERNAL_PORT=$((7680 + i))
  PASSWORD=$(jq -r ".labs[$((i-1))].password" "$CREDS_FILE")

  ttyd -W \
    -p "$INTERNAL_PORT" \
    -b "/lab/${i}" \
    -m 1 \
    -c "lab${i}:${PASSWORD}" \
    -t fontSize=15 \
    -t fontFamily="'JetBrains Mono','Fira Code','Cascadia Code',monospace" \
    -t disableLeaveAlert=true \
    -t enableSixel=false \
    /usr/local/bin/lab-shell.sh "$i" &

  echo "    [+] Lab ${i} → :${INTERNAL_PORT} (user=lab${i})"
done

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        ✅  CyberHX Lab is LIVE on port ${PORT}            ║"
echo "║                                                        ║"
echo "║  Landing   : https://<host>/                           ║"
echo "║  Admin     : https://<host>/admin  (pw in logs above)  ║"
echo "║  Labs      : https://<host>/lab/1/ … /lab/${MAX_LABS}/       ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Start session manager in background ──────────────────────────
/session-manager.sh &
SESSION_MGR_PID=$!

# ── Keep container alive — restart crashed ttyd instances ────────
cleanup() {
  echo "[!] Shutting down..."
  kill "$SESSION_MGR_PID" 2>/dev/null
  for i in $(seq 1 "$MAX_LABS"); do
    pkill -u "lab${i}" 2>/dev/null || true
  done
  nginx -s stop 2>/dev/null || true
  kill "$(cat /var/run/tinyproxy/tinyproxy.pid 2>/dev/null)" 2>/dev/null || true
  exit 0
}
trap cleanup SIGTERM SIGINT

# Watchdog: restart crashed ttyd
while true; do
  sleep 30
  for i in $(seq 1 "$MAX_LABS"); do
    INTERNAL_PORT=$((7680 + i))
    if ! ss -tlnp 2>/dev/null | grep -q ":${INTERNAL_PORT} " && \
       ! netstat -tlnp 2>/dev/null | grep -q ":${INTERNAL_PORT} "; then
      PASSWORD=$(jq -r ".labs[$((i-1))].password" "$CREDS_FILE")
      echo "[watchdog] Restarting lab ${i} on :${INTERNAL_PORT}"
      ttyd -W \
        -p "$INTERNAL_PORT" \
        -b "/lab/${i}" \
        -m 1 \
        -c "lab${i}:${PASSWORD}" \
        -t fontSize=15 \
        -t fontFamily="'JetBrains Mono','Fira Code','Cascadia Code',monospace" \
        -t disableLeaveAlert=true \
        -t enableSixel=false \
        /usr/local/bin/lab-shell.sh "$i" &
    fi
  done
done
