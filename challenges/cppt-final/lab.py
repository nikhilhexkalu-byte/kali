#!/usr/bin/env python3
"""
CPPT Final Practical — Multi-service lab network.

Spawns 5 vulnerable services on separate IPs (127.10.{SLOT}.10-14),
simulating a corporate network the student must pentest.

Each service has a distinct vulnerability and answers a specific
question on the exam. The flag is only reachable through a chain.
"""
import http.server
import json
import html
import os
import subprocess
import sqlite3
import threading
import urllib.parse
import hashlib
import base64

SLOT = int(os.environ.get('CHX_LAB_NUM', '1'))
FLAG = os.environ.get('CHX_FLAG', 'CHX{test_flag}')
NET = f'127.10.{SLOT}'

DB_PATH = f'/srv/challenge/lab{SLOT}/company.db'
BACKUP_DIR = f'/srv/challenge/lab{SLOT}/backup'

CORP_CREDS = {'jsmith': 'Summer2024!', 'admin': 'Pr0dAdmin#1'}
DB_ADMIN_CREDS = ('dbadmin', 'dbadmin123')
API_KEY = 'acme_api_7f8a2b3c4d5e6f1a2b3c4d5e'

CSS = '''*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#0f1923;color:#c8d6e5}
.wrap{max-width:600px;margin:40px auto;padding:20px}
.card{background:#1a2332;border:1px solid #2d3748;border-radius:8px;padding:24px;margin:16px 0}
h1,h2{color:#48dbfb;margin-bottom:12px;font-size:1.3em}
input,textarea{width:100%;background:#0f1923;border:1px solid #2d3748;border-radius:6px;padding:10px;color:#e2e8f0;margin:6px 0;font-family:inherit}
button{background:#48dbfb;color:#0f1923;border:none;border-radius:6px;padding:10px 20px;font-weight:bold;cursor:pointer;margin:8px 0}
button:hover{background:#0abde3}
pre{background:#0a0e14;border:1px solid #2d3748;border-radius:6px;padding:16px;overflow-x:auto;font-size:.85em;color:#a0aec0}
a{color:#48dbfb}
table{width:100%;border-collapse:collapse;margin:12px 0}
th,td{border:1px solid #2d3748;padding:8px;text-align:left;font-size:.85em}
th{background:#1a2332;color:#48dbfb}
.err{color:#ff6b6b;font-size:.9em}
.ok{color:#2ecc71;font-size:.9em}
.tag{display:inline-block;background:#2d3748;border-radius:4px;padding:2px 8px;font-size:.75em;color:#a0aec0;margin:2px}
.nav{background:#1a2332;border-bottom:1px solid #2d3748;padding:12px 20px;display:flex;align-items:center;gap:12px}
.nav a{color:#a0aec0;text-decoration:none;font-size:.85em}
.nav a:hover{color:#48dbfb}'''


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT, password_hash TEXT, department TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY, timestamp TEXT, action TEXT, user TEXT, detail TEXT)')
    users = [
        (1, 'John Smith', 'jsmith@acmecorp.local', 'admin', hashlib.md5(b'Summer2024!').hexdigest(), 'IT'),
        (2, 'Alice Chen', 'achen@acmecorp.local', 'user', hashlib.md5(b'Welcome1').hexdigest(), 'Engineering'),
        (3, 'Bob Wilson', 'bwilson@acmecorp.local', 'user', hashlib.md5(b'Password123').hexdigest(), 'Marketing'),
        (4, 'Carol Davis', 'cdavis@acmecorp.local', 'manager', hashlib.md5(b'Manager#22').hexdigest(), 'HR'),
        (5, 'Dave Kumar', 'dkumar@acmecorp.local', 'admin', hashlib.md5(b'Pr0dAdmin#1').hexdigest(), 'IT'),
        (6, 'Eve Torres', 'etorres@acmecorp.local', 'user', hashlib.md5(b'Spring2025').hexdigest(), 'Finance'),
        (7, 'Frank Lee', 'flee@acmecorp.local', 'user', hashlib.md5(b'Changeme!').hexdigest(), 'Engineering'),
    ]
    c.executemany('INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)', users)
    configs = [
        ('app.version', '3.2.1'),
        ('db.version', 'SQLite 3.39.4'),
        ('api.secret_key', API_KEY),
        ('smtp.host', f'{NET}.15'),
        ('internal.network', f'{NET}.0/24'),
        ('backup.schedule', 'daily 02:00 UTC'),
        ('debug.mode', 'true'),
    ]
    c.executemany('INSERT OR REPLACE INTO config VALUES (?,?)', configs)
    conn.commit()
    conn.close()


def create_backup_files():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(f'{BACKUP_DIR}/ssh_config.bak', 'w') as f:
        f.write(f"""# SSH Config Backup — AcmeCorp Internal
# Last updated: 2026-09-15

Host webserver
  HostName {NET}.10
  User deploy
  Port 22

Host dbserver
  HostName {NET}.12
  User {DB_ADMIN_CREDS[0]}
  Port 22

Host api-internal
  HostName {NET}.13
  User apiuser
  Port 22

# Default credentials for staging (CHANGE BEFORE PROD!)
# DB Admin: {DB_ADMIN_CREDS[0]} / {DB_ADMIN_CREDS[1]}
# API Key: {API_KEY}
""")
    with open(f'{BACKUP_DIR}/network_map.txt', 'w') as f:
        f.write(f"""AcmeCorp Internal Network Map
=============================
{NET}.10  - Corporate Web Portal (Apache 2.4.54)
{NET}.11  - File Server (nginx 1.24.0)
{NET}.12  - Database Admin Panel (Adminer 4.8.1)
{NET}.13  - Internal REST API (Node.js 18.x)
{NET}.14  - Admin Dashboard (CyberHX Admin v2.1.0)

Gateway: {NET}.1
DNS: {NET}.1
""")
    with open(f'{BACKUP_DIR}/changelog.md', 'w') as f:
        f.write("""# AcmeCorp Changelog

## 2026-09-10
- Deployed new diagnostic tool on admin dashboard
- TODO: sanitize user input on diagnostic endpoint

## 2026-08-22
- API v2 launched — added /api/users endpoint
- NOTE: auth middleware not yet applied to all routes

## 2026-07-15
- Migrated database to SQLite (from PostgreSQL)
- Adminer panel deployed for quick access
""")


# ── Service 1: Corporate Web Portal ──────────────────────────────
class CorporateWebHandler(http.server.BaseHTTPRequestHandler):
    """SQLi on login. Reveals employee list on success."""
    server_version = 'Apache/2.4.54'

    def do_GET(self):
        if self.path == '/':
            self._page('AcmeCorp Portal', f'''
<div class="card">
<h1>AcmeCorp Employee Portal</h1>
<p style="color:#a0aec0;margin-bottom:16px">Internal access only. Authenticate to continue.</p>
<form method="POST" action="/login">
<label style="font-size:.8em;color:#718096">Username</label>
<input name="username" placeholder="e.g. jsmith">
<label style="font-size:.8em;color:#718096">Password</label>
<input name="password" type="password">
<button type="submit">Sign In</button>
</form>
<p style="font-size:.75em;color:#4a5568;margin-top:12px">AcmeCorp Portal v3.2.1 — Powered by Apache/2.4.54</p>
</div>''')
        elif self.path == '/robots.txt':
            self._text('User-agent: *\nDisallow: /admin\nDisallow: /backup\nDisallow: /api\n')
        else:
            self._error(404, 'Not Found')

    def do_POST(self):
        if self.path == '/login':
            data = self._form_data()
            user = data.get('username', '')
            pw = data.get('password', '')
            conn = sqlite3.connect(DB_PATH)
            try:
                query = f"SELECT * FROM users WHERE name='{user}' OR email LIKE '%{user}%'"
                rows = conn.execute(query).fetchall()
            except Exception as e:
                self._page('Error', f'<div class="card"><p class="err">Database error: {html.escape(str(e))}</p><p style="font-size:.8em;color:#4a5568">Query: {html.escape(query)}</p><a href="/">Back</a></div>')
                conn.close()
                return
            conn.close()
            if rows:
                table = '<table><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Department</th></tr>'
                for r in rows:
                    table += f'<tr><td>{r[0]}</td><td>{html.escape(str(r[1]))}</td><td>{html.escape(str(r[2]))}</td><td><span class="tag">{html.escape(str(r[3]))}</span></td><td>{html.escape(str(r[5]))}</td></tr>'
                table += '</table>'
                self._page('Portal', f'<div class="card"><h2>Employee Directory</h2>{table}<p style="margin-top:12px"><a href="/">Logout</a></p></div>')
            else:
                self._page('Login Failed', '<div class="card"><p class="err">Invalid credentials.</p><a href="/">Try again</a></div>')
        else:
            self._error(404, 'Not Found')

    def _form_data(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode()
        return dict(urllib.parse.parse_qsl(body))

    def _page(self, title, body):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Server', self.server_version)
        self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>'.encode())

    def _text(self, t):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(t.encode())

    def _error(self, code, msg):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(f'<h1>{code} {msg}</h1>'.encode())

    def log_message(self, *a): pass


# ── Service 2: File Server ───────────────────────────────────────
class FileServerHandler(http.server.BaseHTTPRequestHandler):
    """Directory listing enabled. Leaks SSH creds and network map."""
    server_version = 'nginx/1.24.0'

    def do_GET(self):
        if self.path == '/' or self.path == '/files/':
            files = []
            if os.path.isdir(BACKUP_DIR):
                files = sorted(os.listdir(BACKUP_DIR))
            listing = ''.join(f'<tr><td><a href="/files/{html.escape(f)}">{html.escape(f)}</a></td><td>{os.path.getsize(os.path.join(BACKUP_DIR,f))} bytes</td></tr>' for f in files)
            self._page('File Server', f'''
<div class="card">
<h1>AcmeCorp File Server</h1>
<p style="color:#718096;margin-bottom:12px">Index of /backup/</p>
<table><tr><th>Name</th><th>Size</th></tr>{listing}</table>
<p style="font-size:.7em;color:#4a5568;margin-top:16px">nginx/1.24.0 — Directory listing enabled</p>
</div>''')
        elif self.path.startswith('/files/'):
            fname = os.path.basename(urllib.parse.unquote(self.path[7:]))
            fpath = os.path.join(BACKUP_DIR, fname)
            real = os.path.realpath(fpath)
            if not real.startswith(os.path.realpath(BACKUP_DIR)):
                self._error(403, 'Forbidden')
                return
            if os.path.isfile(fpath):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                with open(fpath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self._error(404, 'File not found')
        else:
            self._error(404, 'Not Found')

    def _page(self, title, body):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Server', self.server_version)
        self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>'.encode())

    def _error(self, code, msg):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(f'<h1>{code} {msg}</h1>'.encode())

    def log_message(self, *a): pass


# ── Service 3: Database Admin Panel ──────────────────────────────
class DatabaseAdminHandler(http.server.BaseHTTPRequestHandler):
    """Default credentials. Exposes user data and config."""
    server_version = 'Adminer/4.8.1'

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        session = self.headers.get('Cookie', '')

        if self.path == '/':
            self._page('Adminer — Login', f'''
<div class="card">
<h1>Adminer 4.8.1</h1>
<p style="color:#718096;margin-bottom:12px">Database management in a single PHP file</p>
<form method="POST" action="/login">
<label style="font-size:.8em;color:#718096">Username</label>
<input name="username" value="dbadmin">
<label style="font-size:.8em;color:#718096">Password</label>
<input name="password" type="password">
<button type="submit">Login</button>
</form>
<p style="font-size:.7em;color:#4a5568;margin-top:8px">SQLite 3.39.4</p>
</div>''')
        elif self.path == '/dashboard' and 'auth=ok' in session:
            conn = sqlite3.connect(DB_PATH)
            users = conn.execute('SELECT id,name,email,role,department FROM users').fetchall()
            configs = conn.execute('SELECT key,value FROM config').fetchall()
            conn.close()
            utable = '<table><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Dept</th></tr>'
            for u in users:
                utable += f'<tr><td>{u[0]}</td><td>{html.escape(str(u[1]))}</td><td>{html.escape(str(u[2]))}</td><td>{html.escape(str(u[3]))}</td><td>{html.escape(str(u[4]))}</td></tr>'
            utable += '</table>'
            ctable = '<table><tr><th>Key</th><th>Value</th></tr>'
            for c in configs:
                ctable += f'<tr><td>{html.escape(str(c[0]))}</td><td><code>{html.escape(str(c[1]))}</code></td></tr>'
            ctable += '</table>'
            self._page('Adminer — Dashboard', f'''
<div class="nav"><a href="/dashboard">Tables</a><a href="/">Logout</a><span style="margin-left:auto;font-size:.75em;color:#4a5568">SQLite 3.39.4 | {len(users)} users</span></div>
<div class="wrap">
<div class="card"><h2>users ({len(users)} rows)</h2>{utable}</div>
<div class="card"><h2>config ({len(configs)} rows)</h2>{ctable}</div>
</div>''')
        else:
            self._page('Unauthorized', '<div class="card"><p class="err">Not authenticated.</p><a href="/">Login</a></div>')

    def do_POST(self):
        if self.path == '/login':
            data = self._form_data()
            if data.get('username') == DB_ADMIN_CREDS[0] and data.get('password') == DB_ADMIN_CREDS[1]:
                self.send_response(302)
                self.send_header('Set-Cookie', 'auth=ok; Path=/')
                self.send_header('Location', '/dashboard')
                self.end_headers()
            else:
                self._page('Login Failed', '<div class="card"><p class="err">Invalid credentials.</p><a href="/">Try again</a></div>')

    def _form_data(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode()
        return dict(urllib.parse.parse_qsl(body))

    def _page(self, title, body):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>'.encode())

    def log_message(self, *a): pass


# ── Service 4: Internal REST API ─────────────────────────────────
class InternalApiHandler(http.server.BaseHTTPRequestHandler):
    """IDOR on /api/users/{id}, unauthenticated /api/config."""
    server_version = 'Express/4.18.2'

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if self.path == '/':
            self._json({'service': 'AcmeCorp Internal API', 'version': '2.0.3', 'docs': '/api/docs'})
        elif self.path == '/api/docs':
            self._json({
                'endpoints': [
                    {'method': 'GET', 'path': '/api/users/{id}', 'auth': 'API key required'},
                    {'method': 'GET', 'path': '/api/users', 'auth': 'API key required'},
                    {'method': 'GET', 'path': '/api/config', 'auth': 'Internal only'},
                    {'method': 'GET', 'path': '/api/health', 'auth': 'None'},
                ]
            })
        elif self.path == '/api/health':
            self._json({'status': 'healthy', 'uptime': '47d 12h', 'version': '2.0.3'})
        elif self.path == '/api/config':
            conn = sqlite3.connect(DB_PATH)
            configs = dict(conn.execute('SELECT key,value FROM config').fetchall())
            conn.close()
            self._json({'config': configs})
        elif self.path.startswith('/api/users'):
            parts = self.path.rstrip('/').split('/')
            conn = sqlite3.connect(DB_PATH)
            if len(parts) == 4 and parts[3].isdigit():
                uid = int(parts[3])
                row = conn.execute('SELECT id,name,email,role,password_hash,department FROM users WHERE id=?', (uid,)).fetchone()
                conn.close()
                if row:
                    self._json({'user': {'id': row[0], 'name': row[1], 'email': row[2], 'role': row[3], 'password_hash': row[4], 'department': row[5]}})
                else:
                    self._json({'error': 'User not found'}, 404)
            else:
                rows = conn.execute('SELECT id,name,email,role,department FROM users').fetchall()
                conn.close()
                self._json({'users': [{'id': r[0], 'name': r[1], 'email': r[2], 'role': r[3], 'department': r[4]} for r in rows], 'total': len(rows)})
        else:
            self._json({'error': 'Not found'}, 404)

    def _json(self, obj, code=200):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('X-Powered-By', 'Express')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a): pass


# ── Service 5: Admin Dashboard (flag is here) ────────────────────
class AdminDashboardHandler(http.server.BaseHTTPRequestHandler):
    """Command injection in diagnostic tool. Flag via SUID privesc."""
    server_version = 'CyberHX-Admin/2.1.0'

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if self.path == '/':
            self._page('Admin Dashboard', f'''
<div class="nav"><span style="color:#48dbfb;font-weight:bold">CyberHX Admin</span>
<a href="/status">System Status</a><a href="/diagnostic">Diagnostic</a><a href="/logs">Logs</a>
<span style="margin-left:auto;font-size:.7em;color:#4a5568">v2.1.0</span></div>
<div class="wrap">
<div class="card"><h2>Admin Dashboard</h2>
<p style="color:#a0aec0">Welcome to the CyberHX administration panel.</p>
<p style="color:#718096;font-size:.85em;margin-top:8px">Network: {NET}.0/24 | Services: 5 active</p>
</div></div>''')
        elif self.path == '/status':
            self._page('System Status', f'''
<div class="nav"><span style="color:#48dbfb;font-weight:bold">CyberHX Admin</span>
<a href="/">Home</a><a href="/diagnostic">Diagnostic</a></div>
<div class="wrap"><div class="card"><h2>System Status</h2>
<pre>Hostname:   admin.acmecorp.local
OS:         Kali GNU/Linux
Kernel:     6.x
Uptime:     47 days
Services:   5/5 running
Network:    {NET}.0/24
Software:   CyberHX Admin v2.1.0</pre></div></div>''')
        elif parsed.path == '/diagnostic':
            target = params.get('target', [''])[0]
            result = ''
            if target:
                try:
                    result = subprocess.check_output(
                        f'ping -c 2 -W 3 {target}',
                        shell=True, stderr=subprocess.STDOUT, timeout=15
                    ).decode(errors='replace')
                except subprocess.CalledProcessError as e:
                    result = e.output.decode(errors='replace')
                except subprocess.TimeoutExpired:
                    result = 'Request timed out'
            self._page('Network Diagnostic', f'''
<div class="nav"><span style="color:#48dbfb;font-weight:bold">CyberHX Admin</span>
<a href="/">Home</a><a href="/status">Status</a></div>
<div class="wrap"><div class="card">
<h2>Network Diagnostic Tool</h2>
<form><label style="font-size:.8em;color:#718096">Target Host</label>
<input name="target" value="{html.escape(target)}" placeholder="IP or hostname">
<button type="submit">Run Diagnostic</button></form>
</div>
{'<div class="card"><h2>Result</h2><pre>' + html.escape(result) + '</pre></div>' if target else ''}
</div>''')
        elif self.path == '/logs':
            self._page('Logs', '''
<div class="nav"><span style="color:#48dbfb;font-weight:bold">CyberHX Admin</span>
<a href="/">Home</a><a href="/diagnostic">Diagnostic</a></div>
<div class="wrap"><div class="card"><h2>Recent Logs</h2>
<pre>[2026-10-11 02:00] Backup completed successfully
[2026-10-10 14:22] User jsmith logged in from 10.0.0.5
[2026-10-10 09:15] Diagnostic tool executed: target=10.10.10.1
[2026-10-09 23:45] Config reload triggered
[2026-10-09 18:30] New user apiuser created (role: service)</pre></div></div>''')
        else:
            self._error(404)

    def _page(self, title, body):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>'.encode())

    def _error(self, code):
        self.send_response(code)
        self.end_headers()

    def log_message(self, *a): pass


def serve(ip, port, handler):
    server = http.server.HTTPServer((ip, port), handler)
    server.serve_forever()


def main():
    init_db()
    create_backup_files()

    services = [
        (f'{NET}.10', 80, CorporateWebHandler, 'Corporate Web Portal'),
        (f'{NET}.11', 80, FileServerHandler, 'File Server'),
        (f'{NET}.12', 80, DatabaseAdminHandler, 'Database Admin'),
        (f'{NET}.13', 80, InternalApiHandler, 'Internal API'),
        (f'{NET}.14', 80, AdminDashboardHandler, 'Admin Dashboard'),
    ]

    for ip, port, handler, name in services:
        t = threading.Thread(target=serve, args=(ip, port, handler), daemon=True)
        t.start()
        print(f'  [{name}] listening on {ip}:{port}')

    print(f'\nLab network ready: {NET}.0/24 ({len(services)} services)')
    threading.Event().wait()


if __name__ == '__main__':
    main()
