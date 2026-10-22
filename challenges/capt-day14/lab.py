#!/usr/bin/env python3
"""CAPT Day 14: Pentest Reporting — find vulns, submit structured report."""
import http.server, os, json, html, sqlite3
from urllib.parse import parse_qs, urlparse

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

db = sqlite3.connect(':memory:', check_same_thread=False)
db.execute('CREATE TABLE reports (id INTEGER PRIMARY KEY, title TEXT, author TEXT)')
db.execute("INSERT INTO reports VALUES (1, 'Q3 Security Audit', 'admin')")
db.execute("INSERT INTO reports VALUES (2, 'Pentest Summary', 'analyst')")
db.commit()

REQUIRED = {'title': 10, 'severity': 3, 'description': 20, 'steps_to_reproduce': 20, 'impact': 10}

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path)
        path, qs = p.path.rstrip('/') or '/', parse_qs(p.query)
        if path == '/':
            self._html('''<h1>Vulnerability Report Portal</h1>
<p>Find the vulnerabilities in this application, then submit a properly formatted report.</p>
<ul><li><a href="/search?q=test">Search Reports</a> (try special characters)</li>
<li><a href="/feedback">Submit Feedback</a> (test the form)</li>
<li>POST /api/submit-report with a JSON vulnerability report</li></ul>
<h3>Report Format</h3><pre>POST /api/submit-report
Content-Type: application/json
{"title":"...", "severity":"critical|high|medium|low", "description":"...", "steps_to_reproduce":"...", "impact":"..."}</pre>''')
        elif path == '/search':
            q = qs.get('q', [''])[0]
            if not q:
                self._html('<h1>Search</h1><form action="/search"><input name="q"><button>Search</button></form>')
                return
            # SQLi vulnerability
            sql = "SELECT id, title, author FROM reports WHERE title LIKE '%" + q + "%'"
            try:
                rows = db.execute(sql).fetchall()
                trs = ''.join(f'<tr><td>{r[0]}</td><td>{html.escape(str(r[1]))}</td><td>{html.escape(str(r[2]))}</td></tr>' for r in rows)
                self._html(f'<h1>Results for: {html.escape(q)}</h1><table border="1"><tr><th>ID</th><th>Title</th><th>Author</th></tr>{trs}</table>')
            except Exception as e:
                self._html(f'<h1>Error</h1><pre>{html.escape(str(e))}</pre>')
        elif path == '/feedback':
            name = qs.get('name', [''])[0]
            if name:
                # XSS vulnerability — reflected
                self._html(f'<h1>Thanks, {name}!</h1><p>Your feedback has been received.</p>')
            else:
                self._html('<h1>Feedback</h1><form><input name="name" placeholder="Your name"><button>Submit</button></form>')
        elif path == '/api/reports':
            rows = db.execute('SELECT * FROM reports').fetchall()
            self._json([{'id':r[0],'title':r[1],'author':r[2]} for r in rows])
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(ln)
        p = self.path.split('?')[0]
        if p == '/api/submit-report':
            try:
                report = json.loads(raw)
            except:
                self._json({'ok': False, 'error': 'Invalid JSON'}, 400); return
            errors = []
            for field, min_len in REQUIRED.items():
                val = report.get(field, '')
                if not isinstance(val, str) or len(val.strip()) < min_len:
                    errors.append(f'{field}: required, min {min_len} chars')
            valid_sev = {'critical', 'high', 'medium', 'low'}
            if report.get('severity', '').lower() not in valid_sev:
                errors.append(f'severity: must be one of {", ".join(valid_sev)}')
            if errors:
                self._json({'ok': False, 'errors': errors}, 400); return
            self._json({'ok': True, 'flag': FLAG, 'message': 'Report accepted. Excellent work on your vulnerability assessment!'})
        else:
            self.send_response(404); self.end_headers()
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())
    def _json(self, o, code=200):
        self.send_response(code); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(o, indent=2).encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
