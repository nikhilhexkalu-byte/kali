#!/usr/bin/env python3
"""
CyberHX Exam API
Manages a staged pentest exam: 3 stages x 2 labs x 15 min each.
Only one candidate at a time. Stages auto-advance when the timer expires.
"""

import http.server
import json
import os
import subprocess
import threading
import time

# ── Config ──────────────────────────────────────────────────────────
API_PORT = 9090
SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', '900'))
CREDS_FILE = '/tmp/lab-credentials.json'
API_TOKEN_FILE = '/tmp/.api-token'

TTYD_THEME = '{"background":"#0f111a","foreground":"#a6accd","cursor":"#ffcc00","selectionBackground":"#1d3b53","black":"#090b10","red":"#ff5370","green":"#c3e88d","yellow":"#ffcb6b","blue":"#82aaff","magenta":"#c792ea","cyan":"#89ddff","white":"#bfc7d5","brightBlack":"#3b4261","brightRed":"#ff5370","brightGreen":"#c3e88d","brightYellow":"#ffcb6b","brightBlue":"#82aaff","brightMagenta":"#c792ea","brightCyan":"#89ddff","brightWhite":"#ffffff"}'

STAGES = [
    {'id': 1, 'labs': [1, 2], 'name': 'Reconnaissance'},
    {'id': 2, 'labs': [3, 4], 'name': 'Exploitation'},
    {'id': 3, 'labs': [5, 6], 'name': 'Post-Exploitation'},
]

# ── Internal auth token (set by start.sh) ──────────────────────────
_api_token = ''
try:
    with open(API_TOKEN_FILE) as f:
        _api_token = f.read().strip()
except Exception:
    pass


def check_token(handler):
    """Check X-Internal-Token header matches the internal token."""
    if not _api_token:
        return True  # no token file = dev mode
    return handler.headers.get('X-Internal-Token', '') == _api_token


# ── Shared state ────────────────────────────────────────────────────
exam = {
    'status': 'idle',        # idle | running | completed
    'current_stage': 0,      # 0 = not started, 1-3
    'stage_start': 0,        # epoch when current stage began
    'exam_start': 0,         # epoch when exam began
    'completed': [],         # list of completed stage ids
}
lock = threading.Lock()
timer_handle = None
ttyd_procs = {}              # lab_num -> subprocess.Popen


# ── Helpers ─────────────────────────────────────────────────────────
def load_creds():
    with open(CREDS_FILE) as f:
        return json.load(f)


def get_password(lab_num):
    for lab in load_creds()['labs']:
        if lab['id'] == lab_num:
            return lab['password']
    return None


def start_ttyd(lab_num):
    """Launch a ttyd instance for one lab."""
    port = 7680 + lab_num
    pw = get_password(lab_num)
    if not pw:
        print(f'[exam] ERROR: no password for lab {lab_num}')
        return

    # Mark session active (for lab-shell.sh)
    fd = os.open(f'/tmp/.lab-session-{lab_num}', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(str(int(time.time())))

    cmd = [
        'ttyd', '-W',
        '-p', str(port),
        '-b', f'/term/{lab_num}',
        '-m', '2',
        '-c', f'lab{lab_num}:{pw}',
        '-t', 'fontSize=14',
        '-t', "fontFamily='Hack','DejaVu Sans Mono','Liberation Mono','Courier New',monospace",
        '-t', f'theme={TTYD_THEME}',
        '-t', 'disableLeaveAlert=true',
        '-t', 'enableSixel=false',
        '/usr/local/bin/lab-shell.sh', str(lab_num),
    ]

    print(f'[exam] Starting lab {lab_num} on :{port}')
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ttyd_procs[lab_num] = proc


def stop_lab(lab_num):
    """Kill ttyd + user processes for a lab."""
    user = f'lab{lab_num}'
    print(f'[exam] Stopping lab {lab_num}')

    # 1. Kill ttyd process (tracked)
    if lab_num in ttyd_procs:
        try:
            ttyd_procs[lab_num].terminate()
            ttyd_procs[lab_num].wait(timeout=3)
        except Exception:
            try:
                ttyd_procs[lab_num].kill()
            except Exception:
                pass
        del ttyd_procs[lab_num]

    # 2. Kill all user processes
    subprocess.run(['pkill', '-9', '-u', user], capture_output=True)

    # 3. Remove session marker
    try:
        os.remove(f'/tmp/.lab-session-{lab_num}')
    except OSError:
        pass

    # 4. Clean user home dir (keep .bashrc .profile)
    home = f'/home/{user}'
    subprocess.run(
        ['find', home, '-maxdepth', '1',
         '-not', '-name', '.bashrc', '-not', '-name', '.profile',
         '-not', '-name', '.', '-newer', f'{home}/.bashrc',
         '-exec', 'rm', '-rf', '{}', '+'],
        capture_output=True,
    )


# ── Stage management ───────────────────────────────────────────────
def begin_stage(stage_num):
    """Start a stage: write end-time, launch labs, arm timer."""
    global timer_handle
    stage = STAGES[stage_num - 1]
    now = int(time.time())
    end_time = now + SESSION_TIMEOUT

    with lock:
        exam['current_stage'] = stage_num
        exam['stage_start'] = now

    # Write stage end-time (root-only) so lab-shell.sh can sync its countdown
    fd = os.open('/tmp/.stage-end-time', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(str(end_time))

    print(f'[exam] === Stage {stage_num}: {stage["name"]} -- Labs {stage["labs"]} ({SESSION_TIMEOUT}s) ===')

    for lab in stage['labs']:
        start_ttyd(lab)

    # Auto-advance when time runs out
    timer_handle = threading.Timer(SESSION_TIMEOUT, advance)
    timer_handle.daemon = True
    timer_handle.start()


def advance():
    """Move to next stage or finish the exam."""
    with lock:
        cur = exam['current_stage']
    stage = STAGES[cur - 1]

    # Stop current labs
    for lab in stage['labs']:
        stop_lab(lab)

    with lock:
        exam['completed'].append(cur)

    if cur < len(STAGES):
        # Small pause between stages so ttyd ports free up
        time.sleep(2)
        begin_stage(cur + 1)
    else:
        # Exam finished
        try:
            os.remove('/tmp/.stage-end-time')
        except OSError:
            pass
        with lock:
            exam['status'] = 'completed'
            exam['current_stage'] = 0
            exam['stage_start'] = 0
        print('[exam] === EXAM COMPLETE ===')


# ── API actions ─────────────────────────────────────────────────────
def do_start():
    global exam
    with lock:
        if exam['status'] == 'running':
            return {'error': 'Exam already in progress'}, 409
        exam = {
            'status': 'running',
            'current_stage': 0,
            'stage_start': 0,
            'exam_start': int(time.time()),
            'completed': [],
        }
    begin_stage(1)
    return {'ok': True, 'stage': 1}, 200


def do_reset():
    global exam, timer_handle
    # Cancel pending timer
    if timer_handle:
        timer_handle.cancel()
        timer_handle = None

    # Stop every lab
    for s in STAGES:
        for lab in s['labs']:
            stop_lab(lab)

    # Clean up stage-end file
    try:
        os.remove('/tmp/.stage-end-time')
    except OSError:
        pass

    with lock:
        exam = {
            'status': 'idle',
            'current_stage': 0,
            'stage_start': 0,
            'exam_start': 0,
            'completed': [],
        }
    print('[exam] === EXAM RESET ===')
    return {'ok': True}, 200


def do_status(include_creds=False):
    """Return exam status. Credentials only included for authenticated requests."""
    with lock:
        now = int(time.time())
        out = dict(exam)
        out['total_stages'] = len(STAGES)
        out['session_timeout'] = SESSION_TIMEOUT
        out['stages'] = [
            {'id': s['id'], 'name': s['name'], 'labs': s['labs']}
            for s in STAGES
        ]

        if out['status'] == 'running' and out['stage_start'] > 0:
            out['time_remaining'] = max(0, SESSION_TIMEOUT - (now - out['stage_start']))
        else:
            out['time_remaining'] = 0

        if out['current_stage'] > 0:
            stage = STAGES[out['current_stage'] - 1]
            out['stage_name'] = stage['name']

            if include_creds:
                # Only include credentials when request is authenticated
                creds = load_creds()
                out['active_labs'] = [
                    {'id': l['id'], 'user': l['user'],
                     'password': l['password'], 'path': l['path']}
                    for l in creds['labs'] if l['id'] in stage['labs']
                ]
            else:
                # Public status — lab paths only, no passwords
                out['active_labs'] = [
                    {'id': lab_id, 'user': f'lab{lab_id}', 'path': f'/lab/{lab_id}/'}
                    for lab_id in stage['labs']
                ]
        else:
            out['active_labs'] = []
            out['stage_name'] = ''

    return out, 200


def do_admin_labs():
    """Return all lab credentials (admin only)."""
    return load_creds(), 200


# ── HTTP server ─────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # suppress default logs

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/exam/status':
            # Check if request comes from nginx (has internal token) = authenticated
            has_token = check_token(self)
            data, code = do_status(include_creds=has_token)
            self._json(data, code)
        elif self.path == '/api/admin/labs':
            if not check_token(self):
                self._json({'error': 'forbidden'}, 403)
                return
            data, code = do_admin_labs()
            self._json(data, code)
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        if self.path == '/api/exam/start':
            if not check_token(self):
                self._json({'error': 'forbidden'}, 403)
                return
            data, code = do_start()
            self._json(data, code)
        elif self.path == '/api/exam/reset':
            if not check_token(self):
                self._json({'error': 'forbidden'}, 403)
                return
            data, code = do_reset()
            self._json(data, code)
        else:
            self._json({'error': 'not found'}, 404)


# ── Main ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'[exam-api] Starting on :{API_PORT}')
    print(f'[exam-api] Timeout per stage: {SESSION_TIMEOUT}s ({SESSION_TIMEOUT // 60}m)')
    print(f'[exam-api] Stages: {len(STAGES)}')
    for s in STAGES:
        print(f'  Stage {s["id"]}: {s["name"]} -- Labs {s["labs"]}')
    print(f'[exam-api] Internal token: {"loaded" if _api_token else "not set (dev mode)"}')

    srv = http.server.HTTPServer(('127.0.0.1', API_PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('[exam-api] Shutting down')
        srv.shutdown()
