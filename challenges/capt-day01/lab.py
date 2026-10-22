#!/usr/bin/env python3
"""CAPT Day 01: Reconnaissance — hidden paths, robots.txt, enumeration."""
import http.server, os

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

PAGES = {
    '/': '<html><head><title>SecureCorp Portal</title></head><body><h1>Welcome to SecureCorp</h1><p>Employee portal v3.2.1</p><a href="/about">About</a> | <a href="/login">Login</a></body></html>',
    '/about': '<html><body><h1>About SecureCorp</h1><p>Founded 2019. Building secure solutions.</p></body></html>',
    '/login': '<html><body><h1>Employee Login</h1><form method="POST"><input name="user" placeholder="Username"><input name="pass" type="password"><button>Login</button></form></body></html>',
    '/robots.txt': 'User-agent: *\nDisallow: /backup/\nDisallow: /admin-old/\nDisallow: /internal/\n',
    '/admin-old': '<html><body><h1>Admin (Legacy)</h1><p>Migrated to new panel. DB backups in /backup/.</p></body></html>',
    '/internal': '<html><body><h1>Internal Tools</h1><p>Health: OK | Uptime: 42d</p></body></html>',
}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = self.path.split('?')[0].rstrip('/') or '/'
        if p == '/backup/db-dump-2026.sql':
            self._text(f"-- DB backup 2026-10-01\n-- Flag: {FLAG}\nCREATE TABLE users(id INT, name TEXT);")
        elif p == '/backup/config.bak':
            self._text("[database]\nhost=localhost\nuser=admin\npassword=SecureCorp2026!")
        elif p == '/backup' or p == '/backup/':
            self._html('<h1>Index of /backup/</h1><pre><a href="db-dump-2026.sql">db-dump-2026.sql</a>\n<a href="config.bak">config.bak</a></pre>')
        elif p in PAGES:
            ct = 'text/plain' if p == '/robots.txt' else 'text/html'
            self.send_response(200); self.send_header('Content-Type', ct); self.end_headers()
            self.wfile.write(PAGES[p].encode())
        else:
            self.send_response(404); self.send_header('Content-Type','text/html'); self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')
    def do_POST(self):
        self._html('<h1>Invalid credentials</h1><a href="/login">Try again</a>')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _text(self, b):
        self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
