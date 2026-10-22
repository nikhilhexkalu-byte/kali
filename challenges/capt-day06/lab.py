#!/usr/bin/env python3
"""CAPT Day 06: Auth Bypass & IDOR — unprotected API, JWT none alg."""
import http.server, os, json, base64, html
from urllib.parse import parse_qs, urlparse

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

USERS = {
    '1': {'id':1,'username':'admin','email':'admin@app.local','role':'administrator','secret_note':f'Flag: {FLAG}'},
    '2': {'id':2,'username':'john','email':'john@app.local','role':'user','secret_note':'Nothing here'},
    '3': {'id':3,'username':'guest','email':'guest@app.local','role':'viewer','secret_note':'Just a guest'},
}

def make_jwt(payload):
    h = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    return f'{h}.{p}.fakesignature'

def decode_jwt(token):
    parts = token.split('.')
    if len(parts) < 2: return None
    hdr = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
    # VULNERABLE: accepts "none" algorithm
    if hdr.get('alg','').lower() == 'none':
        return payload
    return payload

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip('/') or '/'
        if path == '/':
            self._html('<h1>User Portal</h1><a href="/login">Login</a> | <a href="/api/users/2">My Profile (API)</a>')
        elif path == '/login':
            self._html('<h1>Login</h1><form method="POST"><input name="user"><input name="pass" type="password"><button>Login</button></form>')
        elif path.startswith('/api/users/'):
            uid = path.split('/')[-1]
            user = USERS.get(uid)
            if user:
                self._json(user)
            else:
                self.send_response(404); self.end_headers(); self.wfile.write(b'{"error":"not found"}')
        elif path == '/api/admin':
            auth = self.headers.get('Authorization','')
            if auth.startswith('Bearer '):
                try:
                    payload = decode_jwt(auth[7:])
                    if payload and payload.get('role') == 'administrator':
                        self._json({'admin': True, 'flag': FLAG, 'message': 'Welcome admin'})
                        return
                except: pass
            self.send_response(403); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(b'{"error":"admin role required"}')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        u = body.get('user',[''])[0]
        if u == 'john':
            token = make_jwt({'user':'john','role':'user'})
            self._html(f'<h1>Welcome john</h1><p>Your token: <code>{token}</code></p><p>Use with: Authorization: Bearer &lt;token&gt;</p>')
        else:
            self._html('<h1>Login Failed</h1><a href="/login">Retry</a>')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _json(self, o):
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(o, indent=2).encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
