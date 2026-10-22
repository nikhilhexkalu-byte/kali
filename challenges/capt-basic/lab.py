#!/usr/bin/env python3
"""
CAPT Basic Practical — 3-service beginner pentest lab.

Spawns 3 vulnerable services on 127.20.{SLOT}.10-12:
  .10  SecureBlog     — Web app with default creds, directory listing, SQLi
  .11  FileVault      — File server with exposed backups and credentials
  .12  CommandCenter  — Admin panel with command injection → privesc → flag

Deterministic answers (for exam text questions):
  - Web server version: nginx/1.24.0
  - Blog app version: SecureBlog v2.3.1
  - Admin login: admin / Welcome2026
  - Number of users in DB: 5
  - Admin email: admin@secureblog.local
  - robots.txt disallows: /admin-panel, /backup/, /config
  - FTP/file server version: FileVault/1.0.3
  - Backup filename: credentials.bak
  - DB admin password in backup: DbRoot#2026
  - API key in backup: svk_live_8f3a2b7c9d4e1f6a
  - CommandCenter version: CommandCenter v1.2.0
  - CommandCenter login: sysop / DbRoot#2026
  - OS user found via injection: sysop, root, www-data
  - Total open ports: 3
  - Number of records in users table: 5
"""
import hashlib
import html
import http.server
import json
import os
import sqlite3
import subprocess
import threading
import urllib.parse

SLOT = int(os.environ.get('CHX_LAB_NUM', '1'))
NET = f'127.20.{SLOT}'
SVC_PORT = int(os.environ.get('SVC_PORT', '8100'))
DB_PATH = f'/srv/challenge/lab{SLOT}/data/blog.db'

# ── Fixed credentials and data ───────────────────────────────────
BLOG_ADMIN = {'admin': 'Welcome2026'}
SYSOP_CREDS = ('sysop', 'DbRoot#2026')
API_KEY = 'svk_live_8f3a2b7c9d4e1f6a'

CSS = '''*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;background:#0f1923;color:#c8d6e5}
.wrap{max-width:700px;margin:40px auto;padding:20px}
.card{background:#1a2332;border:1px solid #2d3748;border-radius:8px;padding:24px;margin:16px 0}
h1,h2{color:#48dbfb;margin-bottom:12px;font-size:1.3em}
input,textarea{width:100%;background:#0f1923;border:1px solid #2d3748;border-radius:6px;padding:10px;color:#e2e8f0;margin:6px 0;font-family:inherit}
button{background:#48dbfb;color:#0f1923;border:none;border-radius:6px;padding:10px 20px;font-weight:bold;cursor:pointer;margin:8px 0}
button:hover{background:#0abde3}
pre{background:#0a0e14;border:1px solid #2d3748;border-radius:6px;padding:16px;overflow-x:auto;font-size:.85em;color:#a0aec0;white-space:pre-wrap}
a{color:#48dbfb}
table{width:100%;border-collapse:collapse;margin:12px 0}
th,td{border:1px solid #2d3748;padding:8px;text-align:left;font-size:.85em}
th{background:#1a2332;color:#48dbfb}
.err{color:#ff6b6b;font-size:.9em}
.ok{color:#2ecc71;font-size:.9em}
.tag{display:inline-block;background:#2d3748;border-radius:4px;padding:2px 8px;font-size:.75em;color:#a0aec0;margin:2px}
.file{background:#1a2332;border:1px solid #2d3748;border-radius:6px;padding:12px;margin:8px 0;display:flex;align-items:center;gap:12px}
.file a{font-weight:600}
.file .size{color:#718096;font-size:.8em}'''


# ── Database setup ───────────────────────────────────────────────
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, role TEXT, password_hash TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, title TEXT, author TEXT, content TEXT, created TEXT)')
    users = [
        (1, 'admin', 'admin@secureblog.local', 'administrator', hashlib.md5(b'Welcome2026').hexdigest()),
        (2, 'jdoe', 'jdoe@secureblog.local', 'editor', hashlib.md5(b'Password1').hexdigest()),
        (3, 'asmith', 'asmith@secureblog.local', 'author', hashlib.md5(b'Spring2026').hexdigest()),
        (4, 'mwong', 'mwong@secureblog.local', 'editor', hashlib.md5(b'Qwerty123').hexdigest()),
        (5, 'kpatel', 'kpatel@secureblog.local', 'author', hashlib.md5(b'Welcome1').hexdigest()),
    ]
    c.executemany('INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)', users)
    posts = [
        (1, 'Welcome to SecureBlog', 'admin', 'Welcome to our new company blog platform. This is a test deployment.', '2026-09-01'),
        (2, 'Security Best Practices', 'asmith', 'Always use strong passwords and enable MFA on all accounts.', '2026-09-15'),
        (3, 'Q4 Infrastructure Update', 'jdoe', 'We are migrating to new servers this quarter. Expect brief downtime.', '2026-10-01'),
    ]
    c.executemany('INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?)', posts)
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════════════
# Service 1: SecureBlog (port SVC_PORT, IP .10)
# ════════════════════════════════════════════════════════════════════
class SecureBlogHandler(http.server.BaseHTTPRequestHandler):
    server_version = 'nginx/1.24.0'

    def log_message(self, *a): pass

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/':
            self._homepage()
        elif p == '/robots.txt':
            self._text('User-agent: *\nDisallow: /admin-panel\nDisallow: /backup/\nDisallow: /config\n')
        elif p == '/admin-panel':
            self._login_page()
        elif p == '/backup/':
            self._directory_listing()
        elif p == '/search':
            self._search()
        elif p == '/version':
            self._json({'app': 'SecureBlog', 'version': '2.3.1', 'server': 'nginx/1.24.0'})
        else:
            self._error(404)

    def do_POST(self):
        if self.path == '/admin-panel':
            self._login()
        else:
            self._error(404)

    def _homepage(self):
        conn = sqlite3.connect(DB_PATH)
        posts = conn.execute('SELECT title, author, content, created FROM posts ORDER BY id DESC').fetchall()
        conn.close()
        posts_html = ''
        for t, a, c, d in posts:
            posts_html += f'''<div class="card">
<h2>{html.escape(t)}</h2>
<p style="font-size:.8em;color:#718096">By {html.escape(a)} · {html.escape(d)}</p>
<p style="margin-top:8px">{html.escape(c)}</p>
</div>'''
        self._page('SecureBlog', f'''
<div class="card" style="text-align:center">
<h1>SecureBlog</h1>
<p style="color:#718096">Company Blog Platform · v2.3.1</p>
<form action="/search" method="GET" style="margin-top:12px;display:flex;gap:8px">
<input name="q" placeholder="Search posts..." style="flex:1">
<button type="submit">Search</button>
</form>
</div>
{posts_html}
<p style="text-align:center;font-size:.75em;color:#4a5568;margin-top:20px">SecureBlog v2.3.1 · Powered by nginx/1.24.0</p>''')

    def _search(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        q = params.get('q', [''])[0]
        if not q:
            self._page('Search', '<div class="card"><p>Enter a search term.</p><a href="/">Back</a></div>')
            return
        conn = sqlite3.connect(DB_PATH)
        try:
            query = f"SELECT title, author, content FROM posts WHERE title LIKE '%{q}%' OR content LIKE '%{q}%'"
            rows = conn.execute(query).fetchall()
        except Exception as e:
            self._page('Error', f'<div class="card"><p class="err">SQL Error: {html.escape(str(e))}</p><pre>{html.escape(query)}</pre><a href="/">Back</a></div>')
            conn.close()
            return
        conn.close()
        if rows:
            results = ''
            for t, a, c in rows:
                results += f'<div class="card"><h2>{html.escape(str(t))}</h2><p style="font-size:.8em;color:#718096">By {html.escape(str(a))}</p><p>{html.escape(str(c)[:200])}</p></div>'
            self._page('Search Results', f'<p>{len(rows)} result(s) for "{html.escape(q)}"</p>{results}<a href="/">Back</a>')
        else:
            self._page('Search', f'<div class="card"><p>No results for "{html.escape(q)}".</p><a href="/">Back</a></div>')

    def _login_page(self):
        self._page('Admin Login', '''
<div class="card">
<h1>Admin Panel</h1>
<p style="color:#718096;margin-bottom:16px">SecureBlog Administration</p>
<form method="POST" action="/admin-panel">
<label style="font-size:.8em;color:#718096">Username</label>
<input name="username" placeholder="admin">
<label style="font-size:.8em;color:#718096">Password</label>
<input name="password" type="password">
<button type="submit">Login</button>
</form>
</div>''')

    def _login(self):
        data = self._form_data()
        u = data.get('username', '')
        p = data.get('password', '')
        if BLOG_ADMIN.get(u) == p:
            conn = sqlite3.connect(DB_PATH)
            users = conn.execute('SELECT id, username, email, role FROM users').fetchall()
            conn.close()
            table = '<table><tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th></tr>'
            for uid, un, em, rl in users:
                table += f'<tr><td>{uid}</td><td>{html.escape(un)}</td><td>{html.escape(em)}</td><td><span class="tag">{html.escape(rl)}</span></td></tr>'
            table += '</table>'
            self._page('Dashboard', f'''
<div class="card">
<h1>Admin Dashboard</h1>
<p style="color:#718096">SecureBlog v2.3.1 · Logged in as {html.escape(u)}</p>
</div>
<div class="card">
<h2>User Management ({len(users)} users)</h2>
{table}
</div>
<div class="card">
<h2>System Info</h2>
<pre>Application: SecureBlog v2.3.1
Server: nginx/1.24.0
Database: SQLite 3.39.4
Debug Mode: enabled
Internal Network: {NET}.0/24</pre>
</div>
<a href="/">Logout</a>''')
        else:
            self._page('Login Failed', '<div class="card"><p class="err">Invalid credentials.</p><a href="/admin-panel">Try again</a></div>')

    def _directory_listing(self):
        self._page('Index of /backup/', f'''
<div class="card">
<h2>Index of /backup/</h2>
<div class="file"><span>📄</span><a href="/backup/credentials.bak">credentials.bak</a><span class="size">342 bytes</span></div>
<div class="file"><span>📄</span><a href="/backup/server-info.txt">server-info.txt</a><span class="size">289 bytes</span></div>
<div class="file"><span>📄</span><a href="/backup/changelog.md">changelog.md</a><span class="size">198 bytes</span></div>
</div>''')

    def _form_data(self):
        ln = int(self.headers.get('Content-Length', 0))
        return dict(urllib.parse.parse_qsl(self.rfile.read(ln).decode()))

    def _page(self, title, body):
        self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>'.encode())

    def _text(self, t):
        self.send_response(200); self.send_header('Content-Type', 'text/plain'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(t.encode())

    def _json(self, d):
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(json.dumps(d, indent=2).encode())

    def _error(self, code):
        self.send_response(code); self.send_header('Content-Type', 'text/html'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(f'<h1>{code}</h1>'.encode())


# ════════════════════════════════════════════════════════════════════
# Service 2: FileVault (port SVC_PORT+1, IP .11)
# ════════════════════════════════════════════════════════════════════
class FileVaultHandler(http.server.BaseHTTPRequestHandler):
    server_version = 'FileVault/1.0.3'

    def log_message(self, *a): pass

    FILES = {
        '/': None,
        '/credentials.bak': f"""# Service Credentials Backup
# Last updated: 2026-09-20
# DO NOT SHARE — internal use only

[blog-admin]
username = admin
password = Welcome2026
url = http://{{NET}}.10:{{PORT}}

[commandcenter]
username = sysop
password = DbRoot#2026
url = http://{{NET}}.12:{{PORT2}}

[database]
type = sqlite3
path = /srv/data/blog.db
admin_password = DbRoot#2026

[api]
key = svk_live_8f3a2b7c9d4e1f6a
endpoint = http://{{NET}}.10:{{PORT}}/api/v1
""",
        '/server-info.txt': f"""Server Information
==================
Hostname: filevault-01
OS: Debian 12 (Bookworm)
Kernel: 6.1.0-23-amd64
IP: {{NET}}.11
Services: FileVault/1.0.3 (port {{PORT1}})

Internal Network:
  {{NET}}.10 - SecureBlog (nginx/1.24.0)
  {{NET}}.11 - FileVault (this server)
  {{NET}}.12 - CommandCenter (custom)

Total open ports across network: 3
""",
        '/changelog.md': """# FileVault Changelog

## v1.0.3 (2026-09-18)
- Fixed directory traversal on download endpoint
- Added rate limiting

## v1.0.2 (2026-08-10)
- WARNING: credentials.bak should not be served publicly
- TODO: move backup files to /opt/secure/

## v1.0.1 (2026-07-01)
- Initial deployment
""",
    }

    def do_GET(self):
        p = self.path.split('?')[0]
        port = SVC_PORT
        port1 = SVC_PORT + 1
        port2 = SVC_PORT + 2
        net = NET

        if p == '/':
            self._page('FileVault', f'''
<div class="card" style="text-align:center">
<h1>FileVault</h1>
<p style="color:#718096">Internal File Server · v1.0.3</p>
</div>
<div class="card">
<h2>Public Files</h2>
<div class="file"><span>📄</span><a href="/credentials.bak">credentials.bak</a><span class="size">342 bytes</span></div>
<div class="file"><span>📄</span><a href="/server-info.txt">server-info.txt</a><span class="size">289 bytes</span></div>
<div class="file"><span>📄</span><a href="/changelog.md">changelog.md</a><span class="size">198 bytes</span></div>
</div>
<p style="text-align:center;font-size:.75em;color:#4a5568;margin-top:20px">FileVault/1.0.3</p>''')
        elif p in self.FILES and p != '/':
            content = self.FILES[p]
            content = content.replace('{NET}', net).replace('{PORT}', str(port)).replace('{PORT1}', str(port1)).replace('{PORT2}', str(port2))
            self._text(content)
        else:
            self._error(404)

    def _page(self, title, body):
        self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>'.encode())

    def _text(self, t):
        self.send_response(200); self.send_header('Content-Type', 'text/plain'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(t.encode())

    def _error(self, code):
        self.send_response(code); self.send_header('Content-Type', 'text/html'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(f'<h1>{code} Not Found</h1>'.encode())


# ════════════════════════════════════════════════════════════════════
# Service 3: CommandCenter (port SVC_PORT+2, IP .12)
# ════════════════════════════════════════════════════════════════════
class CommandCenterHandler(http.server.BaseHTTPRequestHandler):
    server_version = 'CommandCenter/1.2.0'
    _authed = set()

    def log_message(self, *a): pass

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/':
            self._login_page()
        elif p == '/dashboard':
            if not self._check_auth():
                self._login_page('Please log in first.')
                return
            self._dashboard()
        elif p == '/version':
            self._json({'app': 'CommandCenter', 'version': '1.2.0'})
        else:
            self._error(404)

    def do_POST(self):
        p = self.path.split('?')[0]
        if p == '/':
            self._do_login()
        elif p == '/diagnostic':
            if not self._check_auth():
                self._login_page('Session expired.')
                return
            self._run_diagnostic()
        else:
            self._error(404)

    def _check_auth(self):
        cookie = self.headers.get('Cookie', '')
        return 'session=active' in cookie

    def _login_page(self, msg=''):
        err = f'<p class="err">{html.escape(msg)}</p>' if msg else ''
        self._page('CommandCenter', f'''
<div class="card" style="text-align:center">
<h1>CommandCenter</h1>
<p style="color:#718096">System Administration · v1.2.0</p>
</div>
<div class="card">
<h2>Login</h2>
{err}
<form method="POST" action="/">
<label style="font-size:.8em;color:#718096">Username</label>
<input name="username" placeholder="sysop">
<label style="font-size:.8em;color:#718096">Password</label>
<input name="password" type="password">
<button type="submit">Login</button>
</form>
</div>''')

    def _do_login(self):
        data = self._form_data()
        u = data.get('username', '')
        p = data.get('password', '')
        if u == SYSOP_CREDS[0] and p == SYSOP_CREDS[1]:
            self.send_response(302)
            self.send_header('Set-Cookie', 'session=active; Path=/')
            self.send_header('Location', '/dashboard')
            self.send_header('Server', self.server_version)
            self.end_headers()
        else:
            self._login_page('Invalid username or password.')

    def _dashboard(self):
        self._page('Dashboard', f'''
<div class="card">
<h1>System Dashboard</h1>
<p style="color:#718096">CommandCenter v1.2.0 · Logged in as sysop</p>
</div>
<div class="card">
<h2>System Status</h2>
<pre>Hostname: commandcenter-01
OS: Debian 12 (Bookworm)
Uptime: 47 days, 3:22
Memory: 1.2G / 4.0G (30%)
Disk: 12G / 50G (24%)
Network: {NET}.12</pre>
</div>
<div class="card">
<h2>Network Diagnostic</h2>
<p style="color:#718096;margin-bottom:12px">Run a diagnostic command on the server.</p>
<form method="POST" action="/diagnostic">
<input name="host" placeholder="Enter hostname or IP to ping">
<button type="submit">Run Diagnostic</button>
</form>
</div>
<div class="card">
<h2>Connected Services</h2>
<table>
<tr><th>Host</th><th>Service</th><th>Status</th></tr>
<tr><td>{NET}.10</td><td>SecureBlog</td><td><span class="ok">●</span> Online</td></tr>
<tr><td>{NET}.11</td><td>FileVault</td><td><span class="ok">●</span> Online</td></tr>
<tr><td>{NET}.12</td><td>CommandCenter</td><td><span class="ok">●</span> Online</td></tr>
</table>
</div>''')

    def _run_diagnostic(self):
        data = self._form_data()
        host = data.get('host', '').strip()
        if not host:
            self._dashboard()
            return
        try:
            result = subprocess.run(
                f'ping -c 2 -W 2 {host}',
                shell=True, capture_output=True, text=True, timeout=10
            )
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            output = 'Command timed out.'
        except Exception as e:
            output = f'Error: {e}'

        self._page('Diagnostic Result', f'''
<div class="card">
<h2>Diagnostic Result</h2>
<p style="color:#718096;margin-bottom:8px">Command: ping -c 2 -W 2 {html.escape(host)}</p>
<pre>{html.escape(output)}</pre>
<a href="/dashboard">Back to Dashboard</a>
</div>''')

    def _form_data(self):
        ln = int(self.headers.get('Content-Length', 0))
        return dict(urllib.parse.parse_qsl(self.rfile.read(ln).decode()))

    def _page(self, title, body):
        self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(f'<!doctype html><html><head><title>{title}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>'.encode())

    def _json(self, d):
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(json.dumps(d, indent=2).encode())

    def _error(self, code):
        self.send_response(code); self.send_header('Content-Type', 'text/html'); self.send_header('Server', self.server_version); self.end_headers()
        self.wfile.write(f'<h1>{code}</h1>'.encode())


# ═══════════════════════════════════════════════════════════════════
# Startup — bind each service to its own loopback IP
# ═══════════════════════════════════════════════════════════════════
def add_loopback(ip):
    subprocess.run(['ip', 'addr', 'add', f'{ip}/32', 'dev', 'lo'], capture_output=True)

def serve(handler_class, ip, port):
    server = http.server.HTTPServer((ip, port), handler_class)
    server.serve_forever()

if __name__ == '__main__':
    init_db()

    services = [
        (SecureBlogHandler,    f'{NET}.10', SVC_PORT,     'SecureBlog'),
        (FileVaultHandler,     f'{NET}.11', SVC_PORT + 1, 'FileVault'),
        (CommandCenterHandler, f'{NET}.12', SVC_PORT + 2, 'CommandCenter'),
    ]

    for _, ip, _, _ in services:
        add_loopback(ip)

    threads = []
    for handler, ip, port, name in services:
        t = threading.Thread(target=serve, args=(handler, ip, port), daemon=True)
        t.start()
        threads.append(t)
        print(f'[+] {name} listening on {ip}:{port}')

    print(f'[*] CAPT lab ready — {len(services)} services on {NET}.10-12')

    for t in threads:
        t.join()
