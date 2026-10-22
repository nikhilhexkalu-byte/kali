#!/usr/bin/env python3
"""CAPT Day 09: SSTI — Python format string injection in greeting card."""
import http.server, os, html as H
from urllib.parse import parse_qs, urlparse

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

# Template context — the flag is accessible through the config object
class Config:
    SECRET_KEY = 'supersecret'
    FLAG = FLAG
    DEBUG = True

config = Config()

TEMPLATE = """<html><head><title>Greeting Card</title></head><body>
<div style="border:3px solid gold;padding:40px;text-align:center;max-width:500px;margin:40px auto;border-radius:16px;background:#fffbe6">
<h1>🎉 Happy Birthday!</h1>
<h2>Dear {name}</h2>
<p>Wishing you all the best!</p>
</div></body></html>"""

class Srv(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            self._html('<h1>Greeting Card Generator</h1><form action="/greet"><input name="name" placeholder="Recipient name" style="width:300px"><button>Create Card</button></form><p>Create a personalized greeting card!</p>')
        elif path == '/greet':
            name = qs.get('name', ['Friend'])[0]
            # VULNERABLE: Python format string injection
            try:
                rendered = TEMPLATE.format(name=name, config=config, self=self, __builtins__=__builtins__)
            except (KeyError, IndexError, AttributeError):
                try:
                    rendered = TEMPLATE.replace('{name}', name)
                except:
                    rendered = f'<h1>Card for {H.escape(name)}</h1>'
            self._html(rendered)
        elif path == '/api/template':
            self._html(f'<pre>{H.escape(TEMPLATE)}</pre><p>Variables: name, config</p>')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), Srv).serve_forever()
