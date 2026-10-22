#!/usr/bin/env python3
"""CAPT Day 02: Web Misconfigurations — default creds, directory listing, .env."""
import http.server, os, html
from urllib.parse import parse_qs

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

FILES = {'report-2026.xlsx': '(binary)', 'notes.txt': 'Meeting notes: quarterly review', 'credentials.bak': 'admin:admin\nbackup:backup123'}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = self.path.split('?')[0].rstrip('/') or '/'
        if p == '/':
            self._html('<h1>Corporate Intranet</h1><a href="/files/">Shared Files</a> | <a href="/admin-panel">Admin</a>')
        elif p == '/files' or p == '/files/':
            listing = ''.join(f'<li><a href="/files/{f}">{f}</a></li>' for f in FILES)
            self._html(f'<h1>Index of /files/</h1><ul>{listing}</ul>')
        elif p.startswith('/files/'):
            name = p[7:]
            if name in FILES:
                self._text(FILES[name])
            else:
                self._404()
        elif p == '/.env':
            self._text(f'DB_HOST=localhost\nDB_USER=root\nDB_PASS=r00tP@ss!\nSECRET_KEY=sk_live_a8f3b2\nADMIN_EMAIL=admin@corp.local')
        elif p == '/admin-panel':
            self._html('<h1>Admin Login</h1><form method="POST" action="/admin-panel"><input name="user" placeholder="Username"><input name="pass" type="password"><button>Login</button></form>')
        elif p == '/debug':
            self._html(f'<h1>Debug Info</h1><pre>Python 3.11.2\nOS: Linux 6.1\nPWD: /srv/app\nDB: sqlite:///data.db\nStack: File "/srv/app/main.py", line 42\n  raise ValueError("debug mode active")</pre>')
        else:
            self._404()
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        p = self.path.split('?')[0]
        if p == '/admin-panel':
            u, pw = body.get('user',[''])[0], body.get('pass',[''])[0]
            if u == 'admin' and pw == 'admin':
                self._html(f'<h1>Admin Dashboard</h1><p>Welcome, admin.</p><div class="flag" style="background:#0a0;color:#fff;padding:16px;border-radius:8px;margin-top:20px">Flag: <code>{FLAG}</code></div>')
            else:
                self._html('<h1>Login Failed</h1><p>Invalid credentials.</p><a href="/admin-panel">Retry</a>')
        else:
            self._404()
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _text(self, b):
        self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers(); self.wfile.write(b.encode())
    def _404(self):
        self.send_response(404); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b'<h1>404</h1>')

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
