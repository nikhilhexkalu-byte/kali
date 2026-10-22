#!/usr/bin/env python3
"""CAPT Day 05: Command Injection — ping tool with os.popen."""
import http.server, os
from urllib.parse import parse_qs

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))
ROOT = os.path.dirname(os.path.abspath(__file__))
FLAG_FILE = os.path.join(os.path.dirname(ROOT), 'flag.txt') if not os.path.exists('/srv/challenge') else '/srv/challenge/' + os.environ.get('CHX_LAB_USER','') + '/flag.txt'

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = self.path.split('?')[0].rstrip('/') or '/'
        if p == '/':
            self._html('<h1>Network Diagnostics</h1><p>Check if a host is reachable.</p><form method="POST" action="/ping"><input name="host" placeholder="Enter hostname or IP" style="width:300px"><button>Ping</button></form>')
        elif p == '/about':
            self._html('<h1>Diagnostic Tool v1.2</h1><p>Internal network diagnostics for sysadmins.</p>')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        host = body.get('host', [''])[0]
        if not host:
            self._html('<h1>Error</h1><p>No host provided.</p><a href="/">Back</a>')
            return
        # VULNERABLE: command injection via string concatenation
        cmd = "ping -c 2 -W 2 " + host
        try:
            output = os.popen(cmd).read()
        except Exception as e:
            output = str(e)
        import html
        self._html(f'<h1>Ping Results</h1><pre>$ {html.escape(cmd)}\n\n{html.escape(output)}</pre><a href="/">Back</a>')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
