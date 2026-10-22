#!/usr/bin/env python3
"""CAPT Day 07: SSRF — image fetcher with bypassable blocklist."""
import http.server, os, json, threading
from urllib.parse import parse_qs, urlparse
import urllib.request

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

# Internal service on port 9999 (same host)
class InternalHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path == '/internal/flag':
            self.send_response(200); self.send_header('Content-Type','text/plain'); self.end_headers()
            self.wfile.write(f'Internal Secret: {FLAG}'.encode())
        elif self.path == '/internal/status':
            self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"internal-api","version":"2.1"}')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')

BLOCKED = ['localhost', '169.254.169.254', 'metadata.google', '0.0.0.0']

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            self._html('<h1>Image Preview Service</h1><form action="/fetch"><input name="url" placeholder="Enter image URL" style="width:400px"><button>Fetch</button></form><p>Fetch any image by URL for preview.</p>')
        elif path == '/fetch':
            url = qs.get('url', [''])[0]
            if not url:
                self._html('<p>No URL provided.</p><a href="/">Back</a>'); return
            # Weak blocklist — blocks "localhost" but not 127.0.0.1
            for b in BLOCKED:
                if b in url.lower():
                    self._html(f'<h1>Blocked</h1><p>Access to {b} is not allowed.</p><a href="/">Back</a>'); return
            try:
                req = urllib.request.Request(url, headers={'User-Agent':'ImageFetcher/1.0'})
                resp = urllib.request.urlopen(req, timeout=5)
                data = resp.read(8192).decode('utf-8', errors='replace')
                import html
                self._html(f'<h1>Fetched Content</h1><pre>{html.escape(data[:4096])}</pre><a href="/">Back</a>')
            except Exception as e:
                import html
                self._html(f'<h1>Fetch Error</h1><pre>{html.escape(str(e))}</pre><a href="/">Back</a>')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

def start_internal():
    s = http.server.HTTPServer(('127.0.0.1', 9999), InternalHandler)
    s.serve_forever()

if __name__ == '__main__':
    threading.Thread(target=start_internal, daemon=True).start()
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
