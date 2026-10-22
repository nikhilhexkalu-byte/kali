#!/usr/bin/env python3
"""CAPT Day 03: SQL Injection — UNION-based SQLi on /search."""
import http.server, os, sqlite3, html
from urllib.parse import parse_qs, urlparse

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

db = sqlite3.connect(':memory:', check_same_thread=False)
db.execute('CREATE TABLE users (id INTEGER, username TEXT, email TEXT, role TEXT)')
db.execute('CREATE TABLE secrets (id INTEGER, name TEXT, value TEXT)')
db.execute("INSERT INTO users VALUES (1,'admin','admin@app.local','administrator')")
db.execute("INSERT INTO users VALUES (2,'john','john@app.local','user')")
db.execute("INSERT INTO users VALUES (3,'sarah','sarah@app.local','user')")
db.execute("INSERT INTO secrets VALUES (1,'flag',?)", (FLAG,))
db.execute("INSERT INTO secrets VALUES (2,'api_key','sk_prod_8a7f3b2c')")
db.commit()

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip('/') or '/'
        qs = parse_qs(p.query)
        if path == '/':
            self._html('<h1>Product Catalog</h1><form action="/search"><input name="q" placeholder="Search products..."><button>Search</button></form><p><a href="/login">Admin Login</a></p>')
        elif path == '/search':
            q = qs.get('q', [''])[0]
            if not q:
                self._html('<h1>Search</h1><p>Enter a search term.</p><a href="/">Back</a>')
                return
            # VULNERABLE: string concatenation
            sql = "SELECT id, username, email FROM users WHERE username LIKE '%" + q + "%' OR email LIKE '%" + q + "%'"
            try:
                rows = db.execute(sql).fetchall()
                trs = ''.join(f'<tr><td>{r[0]}</td><td>{html.escape(str(r[1]))}</td><td>{html.escape(str(r[2]))}</td></tr>' for r in rows)
                self._html(f'<h1>Results for: {html.escape(q)}</h1><table border="1"><tr><th>ID</th><th>Name</th><th>Email</th></tr>{trs}</table><br><a href="/">Back</a>')
            except Exception as e:
                self._html(f'<h1>Database Error</h1><pre>{html.escape(str(e))}</pre><a href="/">Back</a>')
        elif path == '/login':
            self._html('<h1>Admin Login</h1><form method="POST" action="/login"><input name="user"><input name="pass" type="password"><button>Login</button></form>')
        else:
            self._404()
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        u, pw = body.get('user',[''])[0], body.get('pass',[''])[0]
        # Also vulnerable login
        sql = "SELECT * FROM users WHERE username='" + u + "' AND role='administrator'"
        try:
            row = db.execute(sql).fetchone()
            if row:
                self._html(f'<h1>Welcome, {html.escape(str(row[1]))}</h1><p>Role: {row[3]}</p>')
            else:
                self._html('<h1>Login Failed</h1><a href="/login">Retry</a>')
        except Exception as e:
            self._html(f'<h1>Error</h1><pre>{html.escape(str(e))}</pre>')
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _404(self):
        self.send_response(404); self.end_headers(); self.wfile.write(b'404')

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
