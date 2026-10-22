#!/usr/bin/env python3
"""CAPT Day 10: Credential Reuse — leaked creds from one service work on another."""
import os
from aiohttp import web

FLAG = os.environ["CHX_FLAG"]
PORT = int(os.environ["SVC_PORT"])
INTERNAL_PORT = PORT + 1
SLOT = int(os.environ["CHX_LAB_NUM"])
BIND = f"127.20.{SLOT}.10"

# Service A: has a debug page that leaks credentials
SVC_A_HOME = """<!DOCTYPE html><html><head><title>HelpDesk Portal</title></head>
<body><h1>HelpDesk Portal</h1><p>Submit a support ticket.</p>
<form method="POST" action="/ticket"><input name="subject" placeholder="Subject"><br>
<textarea name="body" placeholder="Describe your issue"></textarea><br>
<button type="submit">Submit</button></form></body></html>"""

SVC_A_DEBUG = """<!DOCTYPE html><html><body>
<h1>Debug Info (DO NOT EXPOSE IN PRODUCTION)</h1>
<pre>
APP_ENV=production
DB_HOST=internal-db.corp.local
DB_USER=helpdesk_svc
DB_PASS=H3lpD3sk#S3cur3!
ADMIN_USER=sysadmin
ADMIN_PASS=SysAdm1n@2026
SMTP_USER=mailer@corp.local
SMTP_PASS=M@1l3r2026
</pre></body></html>"""

# Service B: admin login where the reused password works
SVC_B_HOME = """<!DOCTYPE html><html><head><title>Admin Console</title></head>
<body><h1>Admin Console</h1>
<form method="POST" action="/login">
<input name="username" placeholder="Username"><br>
<input name="password" type="password" placeholder="Password"><br>
<button type="submit">Login</button></form></body></html>"""

async def svc_a_index(r): return web.Response(text=SVC_A_HOME, content_type="text/html")
async def svc_a_debug(r): return web.Response(text=SVC_A_DEBUG, content_type="text/html")
async def svc_a_ticket(r): return web.Response(text="<h1>Ticket submitted!</h1>", content_type="text/html")

async def svc_b_index(r): return web.Response(text=SVC_B_HOME, content_type="text/html")
async def svc_b_login(r):
    data = await r.post()
    u = data.get("username", "")
    p = data.get("password", "")
    if u == "sysadmin" and p == "SysAdm1n@2026":
        return web.Response(text=f"<h1>Welcome, sysadmin!</h1><p>Admin Panel Access Granted</p><p>Flag: {FLAG}</p>", content_type="text/html")
    return web.Response(text="<h1>Invalid credentials</h1><a href='/'>Try again</a>", content_type="text/html", status=401)

async def start_svc_b(app_):
    svc_b = web.Application()
    svc_b.router.add_get("/", svc_b_index)
    svc_b.router.add_post("/login", svc_b_login)
    runner = web.AppRunner(svc_b)
    await runner.setup()
    await web.TCPSite(runner, BIND, INTERNAL_PORT).start()

app = web.Application()
app.router.add_get("/", svc_a_index)
app.router.add_get("/debug", svc_a_debug)
app.router.add_post("/ticket", svc_a_ticket)
app.on_startup.append(start_svc_b)

if __name__ == "__main__":
    web.run_app(app, host=BIND, port=PORT, print=lambda *a: None)
