#!/usr/bin/env python3
"""CAPT Day 08: File Upload — extension check bypass, serves uploaded files."""
import http.server, os, html, hashlib, time
from urllib.parse import parse_qs, urlparse

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', '/tmp/uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif'}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            self._html('<h1>File Upload Service</h1><form method="POST" action="/upload" enctype="multipart/form-data"><input type="file" name="file"><button>Upload</button></form><p>Accepted: .jpg, .png, .gif</p><p><a href="/uploads/">View uploads</a></p>')
        elif path == '/uploads' or path == '/uploads/':
            files = os.listdir(UPLOAD_DIR) if os.path.isdir(UPLOAD_DIR) else []
            listing = ''.join(f'<li><a href="/uploads/{f}">{html.escape(f)}</a></li>' for f in files)
            self._html(f'<h1>Uploaded Files</h1><ul>{listing}</ul><a href="/">Upload more</a>')
        elif path.startswith('/uploads/'):
            fname = os.path.basename(path[9:])
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                if 'flag' in qs.get('flag', [''])[0].lower() or qs.get('flag', [''])[0] == 'true':
                    self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers()
                    self.wfile.write(f'<h1>Flag</h1><code>{FLAG}</code>'.encode())
                    return
                # Serve with content type based on extension — HTML files execute!
                ct = 'text/html' if fname.endswith('.html') else 'image/jpeg' if fname.endswith('.jpg') else 'application/octet-stream'
                self.send_response(200); self.send_header('Content-Type', ct); self.end_headers()
                with open(fpath, 'rb') as f: self.wfile.write(f.read())
            else:
                self.send_response(404); self.end_headers(); self.wfile.write(b'File not found')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ct = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct:
            self._html('<h1>Error</h1><p>Use multipart form.</p>'); return
        boundary = ct.split('boundary=')[-1].encode()
        ln = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(ln)
        # Simple multipart parse
        parts = data.split(b'--' + boundary)
        for part in parts:
            if b'filename="' in part:
                fname_start = part.index(b'filename="') + 10
                fname_end = part.index(b'"', fname_start)
                fname = part[fname_start:fname_end].decode()
                # VULNERABLE: only checks the FIRST extension
                first_ext = os.path.splitext(fname)[1].lower()
                body_start = part.index(b'\r\n\r\n') + 4
                body_end = part.rfind(b'\r\n')
                file_data = part[body_start:body_end]
                # Bypass: file.jpg.html passes because splitext gets .html, but check uses first ext
                # Actually let's check last ext but allow double extensions
                ext = '.' + fname.split('.')[-1].lower() if '.' in fname else ''
                base_ext = os.path.splitext(fname.split('.')[0] + '.' + fname.split('.')[1] if fname.count('.') > 1 else fname)[1].lower()
                if base_ext in ALLOWED_EXT or ext in ALLOWED_EXT:
                    safe_name = hashlib.md5(fname.encode()).hexdigest()[:8] + '_' + fname
                    fpath = os.path.join(UPLOAD_DIR, safe_name)
                    with open(fpath, 'wb') as f: f.write(file_data)
                    self._html(f'<h1>Uploaded!</h1><p>File: <a href="/uploads/{html.escape(safe_name)}">{html.escape(safe_name)}</a></p><a href="/">Upload more</a>')
                    return
                else:
                    self._html(f'<h1>Rejected</h1><p>Extension {html.escape(ext)} not allowed. Use .jpg, .png, .gif.</p>')
                    return
        self._html('<h1>No file found</h1>')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
