#!/usr/bin/env python3
"""CAPT Day 11: Privilege Escalation — SUID binary 'finder' to read root flag."""
import os
from aiohttp import web

FLAG = os.environ["CHX_FLAG"]
PORT = int(os.environ["SVC_PORT"])
SLOT = int(os.environ["CHX_LAB_NUM"])
BIND = f"127.20.{SLOT}.10"
ROOT = f"/srv/challenge/{os.environ.get('CHX_LAB_USER', 'test')}"

HOME = f"""<!DOCTYPE html><html><head><title>Server Dashboard</title></head>
<body><h1>Server Dashboard v2.0</h1>
<p>Status: Running | Uptime: 47 days</p>
<h2>System Info</h2>
<pre>OS: Debian 12
Kernel: 6.1.0-23-amd64
User: web-service (uid=1001)
Home: {ROOT}</pre>
<p><em>Note: A maintenance tool called <code>finder</code> is available in the challenge directory with special permissions for file searches.</em></p>
<h2>Quick Links</h2>
<ul><li><a href="/status">Service Status</a></li>
<li><a href="/logs">Recent Logs</a></li></ul></body></html>"""

async def index(r): return web.Response(text=HOME, content_type="text/html")
async def status(r):
    return web.Response(text=f"""<h1>Service Status</h1>
<pre>web-server: active (pid 1234)
database:   active (pid 1235)
Writable dirs: /tmp, {ROOT}/data
SUID binaries: {ROOT}/finder (owner: root)</pre>""", content_type="text/html")
async def logs(r):
    return web.Response(text="""<h1>Recent Logs</h1>
<pre>[INFO] User login: admin (success)
[WARN] Failed auth attempt from 10.0.0.5
[INFO] Backup completed: /srv/backup/db.sql
[INFO] SUID check: /srv/challenge/*/finder has setuid bit set</pre>""", content_type="text/html")

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/status", status)
app.router.add_get("/logs", logs)

if __name__ == "__main__":
    web.run_app(app, host=BIND, port=PORT, print=lambda *a: None)
