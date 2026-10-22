#!/usr/bin/env python3
"""CAPT Day 13: Vulnerability Chaining — SSRF → debug token → command exec."""
import http.server, os, json, html, hashlib, threading
from urllib.parse import parse_qs, urlparse
import urllib.request

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))
DEBUG_TOKEN = hashlib.sha256(('debug-' + FLAG).encode()).hexdigest()[:32]

# Internal admin API on 127.0.0.1:9998
class InternalAdmin(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == '/admin-api/status':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(json.dumps({'status':'ok','debug_token': DEBUG_TOKEN,'hint':'Use this token at /debug?token=<token>&cmd=<cmd>'}).encode())
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            self._html('<h1>Enterprise Portal</h1><p>Internal tools and services.</p><ul><li><a href="/proxy">URL Proxy</a> — fetch internal resources</li><li><a href="/debug">Debug Console</a> — requires token</li></ul>')
        elif path == '/proxy':
            url = qs.get('url', [''])[0]
            if not url:
                self._html('<h1>URL Proxy</h1><form action="/proxy"><input name="url" placeholder="Internal URL" style="width:400px"><button>Fetch</button></form><p>Access internal services through the proxy.</p>')
                return
            # Step 1: SSRF — no meaningful blocklist
            try:
                resp = urllib.request.urlopen(url, timeout=5)
                data = resp.read(8192).decode('utf-8', errors='replace')
                self._html(f'<h1>Proxy Response</h1><pre>{html.escape(data)}</pre><a href="/proxy">Back</a>')
            except Exception as e:
                self._html(f'<h1>Proxy Error</h1><pre>{html.escape(str(e))}</pre><a href="/proxy">Back</a>')
        elif path == '/debug':
            token = qs.get('token', [''])[0]
            cmd = qs.get('cmd', [''])[0]
            if not token:
                self._html('<h1>Debug Console</h1><p>Authentication required. Provide a valid debug token.</p><form action="/debug"><input name="token" placeholder="Debug token"><input name="cmd" placeholder="Command"><button>Execute</button></form>')
                return
            # Step 3: command exec with valid token
            if token != DEBUG_TOKEN:
                self.send_response(403); self.send_header('Content-Type','text/html'); self.end_headers()
                self.wfile.write(b'<h1>403 Forbidden</h1><p>Invalid debug token.</p>')
                return
            if not cmd:
                self._html('<h1>Debug Console</h1><p>Token valid. Enter a command.</p><form action="/debug"><input type="hidden" name="token" value="' + html.escape(token) + '"><input name="cmd" placeholder="Command"><button>Execute</button></form>')
                return
            # Simulated command exec
            if 'flag' in cmd.lower():
                output = FLAG
            elif cmd == 'id':
                output = 'uid=0(root) gid=0(root)'
            elif cmd == 'whoami':
                output = 'root'
            elif cmd.startswith('ls'):
                output = 'app.py\nconfig.json\nflag.txt\ndata/'
            else:
                output = f'(executed: {cmd})'
            self._html(f'<h1>Debug Output</h1><pre>$ {html.escape(cmd)}\n{html.escape(output)}</pre><form action="/debug"><input type="hidden" name="token" value="{html.escape(token)}"><input name="cmd"><button>Run</button></form>')
        elif path == '/admin-api' or path == '/admin-api/status':
            self.send_response(403); self.send_header('Content-Type','text/html'); self.end_headers()
            self.wfile.write(b'<h1>403</h1><p>Admin API is internal only. Access via 127.0.0.1:9998.</p>')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

def start_internal():
    http.server.HTTPServer(('127.0.0.1', 9998), InternalAdmin).serve_forever()

if __name__ == '__main__':
    threading.Thread(target=start_internal, daemon=True).start()
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
