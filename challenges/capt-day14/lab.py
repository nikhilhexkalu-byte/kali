#!/usr/bin/env python3
"""CAPT Day 14: Pentest Reporting — submit a proper pentest report to get the flag."""
import os, json
from aiohttp import web

FLAG = os.environ["CHX_FLAG"]
PORT = int(os.environ["SVC_PORT"])
SLOT = int(os.environ["CHX_LAB_NUM"])
BIND = f"127.20.{SLOT}.10"

HOME = """<!DOCTYPE html><html><head><title>Report Submission Portal</title></head>
<body><h1>CAPT Final Report Submission</h1>
<p>Submit a pentest report as JSON. The report must include:</p>
<ul>
<li><code>title</code> — vulnerability title (string)</li>
<li><code>severity</code> — one of: critical, high, medium, low</li>
<li><code>description</code> — at least 50 characters</li>
<li><code>steps_to_reproduce</code> — array with at least 2 steps</li>
<li><code>impact</code> — at least 30 characters</li>
<li><code>remediation</code> — at least 20 characters</li>
</ul>
<h2>Submit Report</h2>
<form method="POST" action="/submit">
<textarea name="report" rows="20" cols="80" placeholder='{"title":"...","severity":"...","description":"...","steps_to_reproduce":["Step 1","Step 2"],"impact":"...","remediation":"..."}'></textarea><br><br>
<button type="submit">Submit Report</button></form>
<p><em>Tip: You can also POST JSON directly to /api/submit with Content-Type: application/json</em></p>
</body></html>"""

REQUIRED = ["title", "severity", "description", "steps_to_reproduce", "impact", "remediation"]
SEVERITIES = {"critical", "high", "medium", "low"}

def validate_report(report):
    errors = []
    for field in REQUIRED:
        if field not in report:
            errors.append(f"Missing required field: {field}")
    if errors:
        return errors
    if not isinstance(report["title"], str) or len(report["title"]) < 5:
        errors.append("title must be at least 5 characters")
    if report.get("severity", "").lower() not in SEVERITIES:
        errors.append(f"severity must be one of: {', '.join(SEVERITIES)}")
    if not isinstance(report["description"], str) or len(report["description"]) < 50:
        errors.append("description must be at least 50 characters")
    steps = report.get("steps_to_reproduce", [])
    if not isinstance(steps, list) or len(steps) < 2:
        errors.append("steps_to_reproduce must be an array with at least 2 steps")
    if not isinstance(report["impact"], str) or len(report["impact"]) < 30:
        errors.append("impact must be at least 30 characters")
    if not isinstance(report["remediation"], str) or len(report["remediation"]) < 20:
        errors.append("remediation must be at least 20 characters")
    return errors

async def index(r): return web.Response(text=HOME, content_type="text/html")

async def submit_form(r):
    data = await r.post()
    raw = data.get("report", "")
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as e:
        return web.Response(text=f"<h1>Invalid JSON</h1><pre>{e}</pre>", content_type="text/html")
    errors = validate_report(report)
    if errors:
        return web.Response(text=f"<h1>Report Rejected</h1><ul>{''.join(f'<li>{e}</li>' for e in errors)}</ul><a href='/'>Fix and resubmit</a>", content_type="text/html")
    return web.Response(text=f"""<h1>✅ Report Accepted!</h1>
<p>Your pentest report meets all professional standards.</p>
<p><strong>Flag: {FLAG}</strong></p>
<h2>Report Summary</h2>
<pre>{json.dumps(report, indent=2)}</pre>""", content_type="text/html")

async def submit_api(r):
    try:
        report = await r.json()
    except json.JSONDecodeError as e:
        return web.json_response({"ok": False, "error": f"Invalid JSON: {e}"}, status=400)
    errors = validate_report(report)
    if errors:
        return web.json_response({"ok": False, "errors": errors}, status=422)
    return web.json_response({"ok": True, "flag": FLAG, "message": "Report accepted — well done!"})

app = web.Application()
app.router.add_get("/", index)
app.router.add_post("/submit", submit_form)
app.router.add_post("/api/submit", submit_api)

if __name__ == "__main__":
    web.run_app(app, host=BIND, port=PORT, print=lambda *a: None)
