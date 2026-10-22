#!/usr/bin/env python3
"""CAPT Day 13: Vulnerability Chaining — info leak + SSRF + cmd injection = flag."""
import os, subprocess, urllib.request
from aiohttp import web

FLAG = os.environ["CHX_FLAG"]
PORT = int(os.environ["SVC_PORT"])
INTERNAL_PORT = PORT + 1
SLOT = int(os.environ["CHX_LAB_NUM"])
BIND = f"127.20.{SLOT}.10"
ROOT = f"/srv/challenge/{os.environ.get('CHX_LAB_USER', 'test')}"

# --- PUBLIC APP (PORT) ---
HOME = """<!DOCTYPE html><html><head><title>CloudOps Dashboard</title></head>
<body><h1>CloudOps Dashboard</h1>
<ul><li><a href="/status">System Status</a></li>
<li><a href="/health-check">Health Check (URL Probe)</a></li></ul></body></html>"""

STATUS_PAGE = f"""<!DOCTYPE html><html><body>
<h1>System Status</h1>
<pre>App Version: 4.2.1
Environment: production
Internal API: http://{BIND}:{INTERNAL_PORT}
Build: 2026-10-15
Debug: disabled</pre></body></html>"""

HEALTH_FORM = """<!DOCTYPE html><html><body>
<h1>Health Check — URL Probe</h1>
<form method="POST" action="/health-check">
<input name="url" placeholder="URL to probe" size="60"><br><br>
<button type="submit">Check</button></form></body></html>"""

async def index(r): return web.Response(text=HOME, content_type="text/html")
async def status(r): return web.Response(text=STATUS_PAGE, content_type="text/html")
async def health_form(r): return web.Response(text=HEALTH_FORM, content_type="text/html")

async def health_check(r):
    data = await r.post()
    url = data.get("url", "").strip()
    if not url:
        return web.Response(text="<h1>No URL</h1>", content_type="text/html")
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        body = resp.read().decode("utf-8", errors="replace")[:4096]
    except Exception as e:
        body = f"Error: {e}"
    return web.Response(text=f"<h1>Health Check</h1><pre>{body}</pre>", content_type="text/html")

# --- INTERNAL APP (PORT+1) ---
INTERNAL_HOME = """<!DOCTYPE html><html><body>
<h1>Internal Admin API</h1>
<ul><li>GET /admin/run?cmd=&lt;command&gt;</li>
<li>GET /admin/info</li></ul></body></html>"""

async def internal_index(r): return web.Response(text=INTERNAL_HOME, content_type="text/html")
async def internal_info(r):
    return web.json_response({"internal": True, "services": ["db", "cache", "queue"], "hint": "Try /admin/run?cmd=cat+flag.txt"})

async def internal_run(r):
    cmd = r.query.get("cmd", "")
    if not cmd:
        return web.Response(text="Missing cmd parameter")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5,
                                cwd=ROOT, env={**os.environ})
        return web.Response(text=result.stdout + result.stderr)
    except Exception as e:
        return web.Response(text=f"Error: {e}")

async def start_internal(app_):
    internal = web.Application()
    internal.router.add_get("/", internal_index)
    internal.router.add_get("/admin/info", internal_info)
    internal.router.add_get("/admin/run", internal_run)
    runner = web.AppRunner(internal)
    await runner.setup()
    await web.TCPSite(runner, BIND, INTERNAL_PORT).start()

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/status", status)
app.router.add_get("/health-check", health_form)
app.router.add_post("/health-check", health_check)
app.on_startup.append(start_internal)

if __name__ == "__main__":
    web.run_app(app, host=BIND, port=PORT, print=lambda *a: None)
