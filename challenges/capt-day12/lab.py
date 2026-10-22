#!/usr/bin/env python3
"""CAPT Day 12: Sensitive Data Exposure — hardcoded API key in JavaScript."""
import os
from aiohttp import web

FLAG = os.environ["CHX_FLAG"]
PORT = int(os.environ["SVC_PORT"])
SLOT = int(os.environ["CHX_LAB_NUM"])
BIND = f"127.20.{SLOT}.10"

API_KEY = "dvault_key_4f8a2c7b9e1d3f6a0b5c8d2e"

HOME = """<!DOCTYPE html><html><head><title>DataVault SaaS</title>
<script src="/static/app.js"></script></head>
<body><h1>DataVault</h1><p>Secure data management platform.</p>
<div id="app"><p>Loading dashboard...</p></div></body></html>"""

APP_JS = f"""// DataVault Frontend v3.1
// TODO: move to env vars before prod deploy
const API_BASE = "/api/v1";
const API_KEY = "{API_KEY}";
const DEBUG = false;

async function loadDashboard() {{
  const resp = await fetch(API_BASE + "/dashboard", {{
    headers: {{ "X-API-Key": API_KEY }}
  }});
  const data = await resp.json();
  document.getElementById("app").innerHTML = "<p>Dashboard loaded</p>";
}}

// Internal admin endpoint — requires valid API key
// GET /api/v1/secret?key=<API_KEY>

document.addEventListener("DOMContentLoaded", loadDashboard);
"""

async def index(r): return web.Response(text=HOME, content_type="text/html")
async def app_js(r): return web.Response(text=APP_JS, content_type="application/javascript")
async def dashboard(r): return web.json_response({{"status": "ok", "user": "viewer"}})

async def secret(r):
    key = r.query.get("key", "")
    if key == API_KEY:
        return web.json_response({{"flag": FLAG, "secrets": ["db_password=D@t@V4ult!", "admin_token=adm-7x8y9z"]}})
    return web.json_response({{"error": "Invalid API key"}}, status=403)

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/static/app.js", app_js)
app.router.add_get("/api/v1/dashboard", dashboard)
app.router.add_get("/api/v1/secret", secret)

if __name__ == "__main__":
    web.run_app(app, host=BIND, port=PORT, print=lambda *a: None)
