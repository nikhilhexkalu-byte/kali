#!/usr/bin/env python3
"""CAPT Day 10: Credential Reuse — two services, shared password."""
import http.server, os, html
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

SVC_A_CREDS = {'admin': 'W1nt3rSt0rm!'}
SVC_B_CREDS = {'operator': 'W1nt3rSt0rm!'}  # Same password, different user

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip('/') or '/'
        if path == '/':
            self._html('<h1>Multi-Service Portal</h1><ul><li><a href="/serviceA">Service A — File Manager</a></li><li><a href="/serviceB">Service B — Admin Console</a></li></ul>')
        elif path == '/config.bak':
            self._text('[serviceA]\nhost=localhost\nuser=admin\npassword=W1nt3rSt0rm!\nport=8080\n\n[serviceB]\nhost=localhost\nuser=operator\n# password same as serviceA for convenience\nport=8080')
        elif path == '/serviceA':
            self._html('<h1>Service A — File Manager</h1><form method="POST" action="/serviceA/login"><input name="user" placeholder="Username"><input name="pass" type="password"><button>Login</button></form><p>Hint: check /config.bak</p>')
        elif path == '/serviceA/dashboard':
            cookie = SimpleCookie(self.headers.get('Cookie',''))
            if cookie.get('svcA') and cookie['svcA'].value == 'admin':
                self._html('<h1>Service A Dashboard</h1><p>Welcome, admin.</p><p>Files: report.pdf, data.csv, backup.tar.gz</p><p>Note: Service B admin console has the deployment keys.</p>')
            else:
                self.send_response(302); self.send_header('Location','/serviceA'); self.end_headers()
        elif path == '/serviceB':
            self._html('<h1>Service B — Admin Console</h1><form method="POST" action="/serviceB/login"><input name="user" placeholder="Username"><input name="pass" type="password"><button>Login</button></form>')
        elif path == '/serviceB/admin':
            cookie = SimpleCookie(self.headers.get('Cookie',''))
            if cookie.get('svcB') and cookie['svcB'].value == 'operator':
                self._html(f'<h1>Service B Admin Console</h1><p>Welcome, operator.</p><div style="background:#0a0;color:#fff;padding:16px;border-radius:8px">Deployment Key (FLAG): <code>{FLAG}</code></div>')
            else:
                self.send_response(302); self.send_header('Location','/serviceB'); self.end_headers()
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        u, pw = body.get('user',[''])[0], body.get('pass',[''])[0]
        p = self.path.split('?')[0]
        if p == '/serviceA/login':
            if SVC_A_CREDS.get(u) == pw:
                self.send_response(302); self.send_header('Set-Cookie','svcA=admin; Path=/'); self.send_header('Location','/serviceA/dashboard'); self.end_headers()
            else:
                self._html('<h1>Login Failed</h1><a href="/serviceA">Retry</a>')
        elif p == '/serviceB/login':
            if SVC_B_CREDS.get(u) == pw:
                self.send_response(302); self.send_header('Set-Cookie','svcB=operator; Path=/'); self.send_header('Location','/serviceB/admin'); self.end_headers()
            else:
                self._html('<h1>Login Failed</h1><a href="/serviceB">Retry</a>')
        else:
            self.send_response(404); self.end_headers()
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _text(self, b):
        self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
