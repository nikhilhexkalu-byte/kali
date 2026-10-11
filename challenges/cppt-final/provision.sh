#!/bin/bash
# /opt/challenges/cppt-final/provision.sh
# CPPT Final Practical: Web exploitation + privilege escalation
#
# Attack chain:
#   1. Discover web service on 127.0.0.1:PORT (nmap/curl)
#   2. Find command injection in /diagnostic endpoint
#   3. Use injection to enumerate the system → find SUID binary
#   4. Exploit SUID find (GTFOBins) to read the flag as root
#
# Cross-tenant safety:
#   - Challenge dir restricted to lab user's group (mode 750)
#   - SUID binary restricted to lab user's group (mode 4750)
#   - www-chx service user added to lab user's group
#   - Other lab users cannot access the directory, binary, or flag
#   - Even if another user reaches the web port, the exam site
#     verifies flag ownership per-session (unique flags, IDOR-safe)
set -euo pipefail

PORT=$((8000 + CHX_LAB_NUM))
ROOT="/srv/challenge/${CHX_LAB_USER}"

rm -rf "$ROOT"; mkdir -p "$ROOT"

# ── Per-slot service user, added to the lab user's group ──────────
useradd -r -s /usr/sbin/nologin "www-chx${CHX_LAB_NUM}" 2>/dev/null || true
usermod -aG "${CHX_LAB_USER}" "www-chx${CHX_LAB_NUM}" 2>/dev/null || true

# ── Restrict challenge directory to root + lab user's group ───────
chown root:"${CHX_LAB_USER}" "$ROOT"
chmod 750 "$ROOT"

# ── Plant the flag where only root can read it ────────────────────
install -o root -g root -m 600 /dev/null "$ROOT/flag.txt"
printf '%s\n' "$CHX_FLAG" > "$ROOT/flag.txt"

# ── Create a SUID binary for privilege escalation ─────────────────
# Restricted to the lab user's group: other slots cannot execute it.
cp /usr/bin/find "$ROOT/finder"
chown root:"${CHX_LAB_USER}" "$ROOT/finder"
chmod 4750 "$ROOT/finder"

# ── Create the vulnerable web application ─────────────────────────
cat > "$ROOT/server.py" << 'PYEOF'
#!/usr/bin/env python3
"""
CyberHX Network Diagnostic Tool (intentionally vulnerable)
Vuln: OS command injection in /diagnostic via the 'target' parameter.
The app runs as www-chx (not root), so the attacker must combine
the injection with the SUID 'finder' binary to read the flag.
"""
import http.server
import subprocess
import urllib.parse
import os
import html

PORT = int(os.environ['WEBAPP_PORT'])

INDEX = b'''<!doctype html>
<html><head><title>CyberHX Diagnostic Portal</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Courier New',monospace;background:#0a0e17;color:#c5cdd9;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:40px;max-width:520px;width:100%}
h1{color:#00ff88;font-size:1.4rem;margin-bottom:8px}
.sub{color:#6b7280;font-size:.75rem;margin-bottom:24px}
label{display:block;color:#9ca3af;font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
input{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 14px;color:#e6edf3;font-family:inherit;font-size:.9rem}
input:focus{outline:none;border-color:#00ff88}
button{margin-top:12px;width:100%;background:#00ff88;color:#0a0e17;border:none;border-radius:8px;padding:10px;font-weight:bold;cursor:pointer;font-family:inherit;font-size:.9rem}
button:hover{background:#00cc6a}
.footer{margin-top:20px;color:#374151;font-size:.65rem;text-align:center}
</style></head><body>
<div class="card">
<h1>&gt;_ Network Diagnostic</h1>
<p class="sub">Internal tool &mdash; verify connectivity to infrastructure hosts</p>
<form action="/diagnostic" method="GET">
<label for="target">Target host or IP</label>
<input id="target" name="target" placeholder="e.g. 192.168.1.1" required>
<button type="submit">Run Diagnostic</button>
</form>
<div class="footer">CyberHX Infrastructure &bull; Authorized use only</div>
</div></body></html>'''

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(INDEX)
        elif parsed.path == '/diagnostic':
            target = params.get('target', [''])[0]
            if not target:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Missing target parameter')
                return
            try:
                result = subprocess.check_output(
                    f'ping -c 2 -W 3 {target}',
                    shell=True, stderr=subprocess.STDOUT, timeout=15
                ).decode(errors='replace')
            except subprocess.CalledProcessError as e:
                result = e.output.decode(errors='replace')
            except subprocess.TimeoutExpired:
                result = 'Request timed out'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(f'''<!doctype html><html><head><title>Result</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Courier New',monospace;background:#0a0e17;color:#c5cdd9;padding:40px}}
h2{{color:#00ff88;margin-bottom:16px}}pre{{background:#111827;border:1px solid #1f2937;border-radius:8px;padding:20px;overflow-x:auto;font-size:.85rem}}
a{{color:#00ff88;display:inline-block;margin-top:16px}}</style></head><body>
<h2>&gt; ping {html.escape(target)}</h2>
<pre>{html.escape(result)}</pre>
<a href="/">&larr; Back</a></body></html>'''.encode())
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, *a):
        pass

http.server.HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
PYEOF

chmod 640 "$ROOT/server.py"
chown root:"${CHX_LAB_USER}" "$ROOT/server.py"

# ── Start the web app as the per-slot service user ────────────────
WEBAPP_PORT=$PORT nohup su -s /bin/bash -c "WEBAPP_PORT=$PORT python3 $ROOT/server.py" "www-chx${CHX_LAB_NUM}" \
  > /dev/null 2>&1 &

# ── Drop a hint in the lab user's home ────────────────────────────
cat > "${CHX_LAB_HOME}/README.txt" << EOF
=== CPPT Final Practical ===

Your mission: find and exploit a vulnerable internal service
running on this machine, then escalate your privileges to
read the flag.

The flag format is: CHX{...}

Hints:
  - Start with local service discovery
  - Look for common web vulnerabilities
  - Not everything runs as root

Good luck.
EOF
chown "${CHX_LAB_USER}:${CHX_LAB_USER}" "${CHX_LAB_HOME}/README.txt"

echo "provisioned ${CHX_LAB_USER} on :${PORT}"
