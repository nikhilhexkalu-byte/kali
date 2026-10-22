#!/usr/bin/env python3
"""CAPT Day 12: Secrets & Data Exposure — JS files, git history, API keys."""
import http.server, os, json, html, hashlib
from urllib.parse import parse_qs, urlparse

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))
half1 = FLAG[:len(FLAG)//2]
half2 = FLAG[len(FLAG)//2:]
API_KEY = 'dvault_key_' + hashlib.md5(FLAG.encode()).hexdigest()[:16]

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            self._html(f'<html><head><script src="/static/app.js"></script><script src="/static/config.js"></script></head><body><h1>Dashboard</h1><p>Welcome to the analytics dashboard.</p><p id="data">Loading...</p></body></html>')
        elif path == '/static/app.js':
            self._js(f'// App bundle v2.3.1\nconsole.log("App loaded");\n// sourceMappingURL=app.js.map\nfetch("/api/data").then(r=>r.json()).then(d=>document.getElementById("data").textContent=JSON.stringify(d));')
        elif path == '/static/app.js.map':
            self._json({
                'version': 3, 'file': 'app.js',
                'sources': ['src/app.ts', 'src/config.ts'],
                'sourcesContent': [
                    'import {{ config }} from "./config";\nconsole.log(config);',
                    f'// OLD CONFIG — DO NOT COMMIT\nexport const config = {{\n  apiUrl: "/api",\n  secretPart1: "{half1}",\n  debug: true\n}};'
                ]
            })
        elif path == '/static/config.js':
            self._js(f'// Frontend config\nconst CONFIG = {{\n  apiUrl: "/api",\n  apiKey: "{API_KEY}",\n  version: "2.3.1"\n}};')
        elif path == '/api/data':
            self._json({'users': 142, 'revenue': '$12,340', 'uptime': '99.9%'})
        elif path == '/api/git/log':
            self._json([
                {'hash': 'a1b2c3d', 'message': 'update dashboard', 'date': '2026-10-20'},
                {'hash': 'e4f5g6h', 'message': 'remove hardcoded secrets (oops)', 'date': '2026-10-18', 'diff': f'-const SECRET = "{half2}";\n+const SECRET = process.env.SECRET;'},
                {'hash': 'i7j8k9l', 'message': 'initial commit', 'date': '2026-10-15'},
            ])
        elif path == '/api/validate-key':
            key = qs.get('key', [''])[0]
            if key == API_KEY:
                self._json({'valid': True, 'flag': FLAG, 'message': 'API key validated successfully'})
            else:
                self._json({'valid': False, 'message': 'Invalid API key'})
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _js(self, b):
        self.send_response(200); self.send_header('Content-Type','application/javascript'); self.end_headers(); self.wfile.write(b.encode())
    def _json(self, o):
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(o, indent=2).encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
