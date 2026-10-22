#!/usr/bin/env python3
"""CAPT Day 04: XSS — stored & reflected XSS, cookie-gated flag."""
import http.server, os, json, html as H
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))
comments = []

class Srv(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            rows = ''.join(f'<div class="comment"><b>{c["name"]}</b>: {c["text"]}</div>' for c in comments)
            self._html(f'<h1>Guestbook</h1>{rows}<hr><form method="POST"><input name="name" placeholder="Name"><textarea name="text" placeholder="Comment"></textarea><button>Post</button></form><p><a href="/search?q=test">Search</a> | <a href="/flag">Admin Flag</a></p>')
        elif path == '/search':
            q = qs.get('q', [''])[0]
            # Reflected XSS: no escaping
            self._html(f'<h1>Search results for: {q}</h1><p>No results found.</p><a href="/">Back</a>')
        elif path == '/flag':
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            if cookie.get('admin_session') and cookie['admin_session'].value == 'true':
                self._html(f'<h1>Admin Panel</h1><p>Flag: <code>{FLAG}</code></p>')
            else:
                self.send_response(403); self.send_header('Content-Type','text/html'); self.end_headers()
                self.wfile.write(b'<h1>403 Forbidden</h1><p>Admin session required.</p>')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        name = body.get('name', ['Anonymous'])[0]
        text = body.get('text', [''])[0]
        # Stored XSS: no sanitization
        comments.append({'name': name, 'text': text})
        self.send_response(302); self.send_header('Location', '/'); self.end_headers()
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), Srv).serve_forever()
