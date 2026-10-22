#!/usr/bin/env python3
"""
CyberHX Lab API

Two surfaces:

  1. Legacy demo exam  (/api/exam/*)   — the single-player staged walkthrough.
     Kept for local testing. Credentials are NEVER served on the public
     status endpoint; starting it can be locked behind admin auth.

  2. Lease API         (/api/v1/*)     — the multi-tenant integration used by
     pentestlab.cyberhx.com. The site's SERVER (never a browser) leases one
     isolated lab slot per exam attempt, authenticated with an HMAC shared
     secret. Each lease gets a freshly rotated terminal password, its own
     deadline, and optionally a per-attempt flag provisioned by a challenge
     script. Slots are wiped and freed when the lease ends.

Only the Python standard library is used.
"""

import base64
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import subprocess
import threading
import time

# ── Config ──────────────────────────────────────────────────────────
API_PORT = 9090
SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', '900'))
MAX_LABS = int(os.environ.get('MAX_LABS', '6'))
CREDS_FILE = '/tmp/lab-credentials.json'
API_TOKEN_FILE = '/tmp/.api-token'
LEASE_SECRET_FILE = '/tmp/.lease-secret'

# Lease API limits
MAX_LEASE_SECONDS = int(os.environ.get('MAX_LEASE_SECONDS', '21600'))
CLOCK_SKEW_SECONDS = 300
NONCE_TTL = CLOCK_SKEW_SECONDS * 2

# Challenge provisioning (owner-supplied; see CHALLENGES.md)
CHALLENGE_DIR = os.environ.get('CHALLENGE_DIR', '/opt/challenges')
CHALLENGE_ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,47}$')

# Set PUBLIC_DEMO=true to let anonymous visitors start the legacy demo exam.
# Default is false: the demo consumes real lab capacity, so it needs admin auth.
PUBLIC_DEMO = os.environ.get('PUBLIC_DEMO', 'false').strip().lower() == 'true'

TTYD_THEME = '{"background":"#0f111a","foreground":"#a6accd","cursor":"#ffcc00","selectionBackground":"#1d3b53","black":"#090b10","red":"#ff5370","green":"#c3e88d","yellow":"#ffcb6b","blue":"#82aaff","magenta":"#c792ea","cyan":"#89ddff","white":"#bfc7d5","brightBlack":"#3b4261","brightRed":"#ff5370","brightGreen":"#c3e88d","brightYellow":"#ffcb6b","brightBlue":"#82aaff","brightMagenta":"#c792ea","brightCyan":"#89ddff","brightWhite":"#ffffff"}'

STAGES = [
    {'id': 1, 'labs': [1, 2], 'name': 'Reconnaissance'},
    {'id': 2, 'labs': [3, 4], 'name': 'Exploitation'},
    {'id': 3, 'labs': [5, 6], 'name': 'Post-Exploitation'},
]


def _read_secret(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return ''


# ── Internal auth token (set by start.sh) ──────────────────────────
# Proves a request arrived through nginx rather than straight from a lab
# user on localhost:9090. It is NOT an authorization signal: nginx attaches
# it to every proxied request, including anonymous ones.
_api_token = _read_secret(API_TOKEN_FILE)

# ── Lease shared secret (LEASE_SECRET env, written by start.sh) ────
_lease_secret = _read_secret(LEASE_SECRET_FILE)


def via_nginx(handler):
    if not _api_token:
        return True  # no token file = dev mode
    return hmac.compare_digest(handler.headers.get('X-Internal-Token', ''), _api_token)


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

# Slot registry shared by BOTH surfaces so a demo exam and a lease can never
# hand out the same lab. owner is 'demo' or 'lease'.
slots = {
    i: {'owner': None, 'session_id': None, 'attempt_id': None,
        'password': None, 'expires_at': 0, 'challenge_id': None,
        'flag_sha256': None, 'started_at': 0}
    for i in range(1, MAX_LABS + 1)
}
sessions = {}                # session_id -> lab_num
_nonces = {}                 # nonce -> expiry epoch


# ── Helpers ─────────────────────────────────────────────────────────
def load_creds():
    with open(CREDS_FILE) as f:
        return json.load(f)


def get_password(lab_num):
    """Current terminal password for a lab: the rotated one if leased."""
    slot = slots.get(lab_num)
    if slot and slot['password']:
        return slot['password']
    for lab in load_creds()['labs']:
        if lab['id'] == lab_num:
            return lab['password']
    return None


def new_password():
    return base64.b64encode(secrets.token_bytes(18)).decode().replace('+', 'A').replace('/', 'B').replace('=', '')[:20]


def _write_root_only(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(str(value))


def start_ttyd(lab_num, password=None, end_time=None):
    """Launch a ttyd instance for one lab.

    end_time is the epoch this shell must die at. It is written to a per-lab
    file that lab-shell.sh prefers over the shared demo stage clock, so a
    lease of any length counts down correctly and a stale stage file from an
    earlier demo can never cut a leased session short.
    """
    port = 7680 + lab_num
    pw = password or get_password(lab_num)
    if not pw:
        print(f'[lab] ERROR: no password for lab {lab_num}')
        return False

    # Mark session active (for lab-shell.sh)
    _write_root_only(f'/tmp/.lab-session-{lab_num}', int(time.time()))
    if end_time:
        _write_root_only(f'/tmp/.lab-end-time-{lab_num}', int(end_time))
    else:
        try:
            os.remove(f'/tmp/.lab-end-time-{lab_num}')
        except OSError:
            pass

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

    print(f'[lab] Starting lab {lab_num} on :{port}')
    ttyd_procs[lab_num] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def stop_lab(lab_num):
    """Kill ttyd + user processes for a lab and wipe its home directory."""
    user = f'lab{lab_num}'
    print(f'[lab] Stopping lab {lab_num}')

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

    teardown_challenge(lab_num)

    subprocess.run(
        ['/usr/local/bin/lab-cleanup.sh', str(lab_num)],
        capture_output=True, timeout=30,
    )


# ── Challenge provisioning ─────────────────────────────────────────
def _challenge_script(challenge_id, name):
    if not CHALLENGE_ID_RE.match(challenge_id or ''):
        return None
    path = os.path.join(CHALLENGE_DIR, challenge_id, name)
    # Defence in depth: the resolved path must stay inside CHALLENGE_DIR.
    if not os.path.realpath(path).startswith(os.path.realpath(CHALLENGE_DIR) + os.sep):
        return None
    return path if os.path.isfile(path) else None


def provision_challenge(lab_num, challenge_id, flag):
    """Run the owner-supplied provision script for a lease. Returns (ok, error)."""
    script = _challenge_script(challenge_id, 'provision.sh')
    if not script:
        return False, f'challenge "{challenge_id}" is not installed on this lab'
    env = dict(os.environ)
    env.update({
        'CHX_LAB_NUM': str(lab_num),
        'CHX_LAB_USER': f'lab{lab_num}',
        'CHX_LAB_HOME': f'/home/lab{lab_num}',
        'CHX_FLAG': flag,
    })
    try:
        r = subprocess.run([script], env=env, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return False, 'challenge provisioning timed out'
    if r.returncode != 0:
        stdout_snip = r.stdout[:500].decode('utf-8', errors='replace') if isinstance(r.stdout, bytes) else str(r.stdout)[:500]
        stderr_snip = r.stderr[:500].decode('utf-8', errors='replace') if isinstance(r.stderr, bytes) else str(r.stderr)[:500]
        print(f'[lab] provision.sh failed for {challenge_id}:')
        print(f'[lab]   stdout: {stdout_snip!r}')
        print(f'[lab]   stderr: {stderr_snip!r}')
        return False, 'challenge provisioning failed'
    return True, None


def teardown_challenge(lab_num):
    cid = slots.get(lab_num, {}).get('challenge_id')
    if not cid:
        return
    script = _challenge_script(cid, 'teardown.sh')
    if not script:
        return
    env = dict(os.environ)
    env.update({'CHX_LAB_NUM': str(lab_num), 'CHX_LAB_USER': f'lab{lab_num}',
                'CHX_LAB_HOME': f'/home/lab{lab_num}'})
    try:
        subprocess.run([script], env=env, capture_output=True, timeout=60)
    except Exception:
        pass


# ── Slot lifecycle ─────────────────────────────────────────────────
def _free_slot(lab_num):
    s = slots[lab_num]
    if s['session_id']:
        sessions.pop(s['session_id'], None)
    slots[lab_num] = {'owner': None, 'session_id': None, 'attempt_id': None,
                      'password': None, 'expires_at': 0, 'challenge_id': None,
                      'flag_sha256': None, 'started_at': 0}


def release_lease(lab_num):
    stop_lab(lab_num)
    with lock:
        _free_slot(lab_num)


def reap_expired():
    """Background sweep: end leases whose deadline has passed."""
    while True:
        time.sleep(15)
        now = int(time.time())
        due = []
        with lock:
            for n, s in slots.items():
                if s['owner'] == 'lease' and s['expires_at'] and s['expires_at'] <= now:
                    due.append(n)
        for n in due:
            print(f'[lease] Lab {n}: lease expired — reclaiming')
            release_lease(n)


# ── Stage management (legacy demo) ─────────────────────────────────
def begin_stage(stage_num):
    global timer_handle
    stage = STAGES[stage_num - 1]
    now = int(time.time())
    end_time = now + SESSION_TIMEOUT

    with lock:
        exam['current_stage'] = stage_num
        exam['stage_start'] = now

    _write_root_only('/tmp/.stage-end-time', end_time)

    print(f'[demo] === Stage {stage_num}: {stage["name"]} -- Labs {stage["labs"]} ({SESSION_TIMEOUT}s) ===')

    for lab in stage['labs']:
        pw = new_password()
        with lock:
            slots[lab].update({'owner': 'demo', 'password': pw,
                               'expires_at': end_time, 'started_at': now})
        start_ttyd(lab, pw, end_time=end_time)

    timer_handle = threading.Timer(SESSION_TIMEOUT, advance)
    timer_handle.daemon = True
    timer_handle.start()


def advance():
    with lock:
        cur = exam['current_stage']
    stage = STAGES[cur - 1]

    for lab in stage['labs']:
        stop_lab(lab)
        with lock:
            _free_slot(lab)

    with lock:
        exam['completed'].append(cur)

    if cur < len(STAGES):
        time.sleep(2)
        begin_stage(cur + 1)
    else:
        try:
            os.remove('/tmp/.stage-end-time')
        except OSError:
            pass
        with lock:
            exam['status'] = 'completed'
            exam['current_stage'] = 0
            exam['stage_start'] = 0
        print('[demo] === EXAM COMPLETE ===')


# ── Legacy demo actions ────────────────────────────────────────────
def do_start():
    global exam
    with lock:
        if exam['status'] == 'running':
            return {'error': 'Exam already in progress'}, 409
        busy = [n for n, s in slots.items() if s['owner'] == 'lease']
        if busy:
            return {'error': 'Lab capacity is in use by live exam sessions'}, 409
        exam = {'status': 'running', 'current_stage': 0, 'stage_start': 0,
                'exam_start': int(time.time()), 'completed': []}
    begin_stage(1)
    return {'ok': True, 'stage': 1}, 200


def do_reset():
    global exam, timer_handle
    if timer_handle:
        timer_handle.cancel()
        timer_handle = None

    for s in STAGES:
        for lab in s['labs']:
            stop_lab(lab)
            with lock:
                if slots[lab]['owner'] == 'demo':
                    _free_slot(lab)

    try:
        os.remove('/tmp/.stage-end-time')
    except OSError:
        pass

    with lock:
        exam = {'status': 'idle', 'current_stage': 0, 'stage_start': 0,
                'exam_start': 0, 'completed': []}
    print('[demo] === EXAM RESET ===')
    return {'ok': True}, 200


def do_status(include_creds=False):
    """Legacy demo status.

    include_creds is ONLY ever true for admin-authenticated callers. The
    public page gets lab paths and usernames, never passwords — the learner
    receives their password from the authenticated caller that leased the slot.
    """
    with lock:
        now = int(time.time())
        out = dict(exam)
        out['total_stages'] = len(STAGES)
        out['session_timeout'] = SESSION_TIMEOUT
        out['stages'] = [{'id': s['id'], 'name': s['name'], 'labs': s['labs']} for s in STAGES]

        if out['status'] == 'running' and out['stage_start'] > 0:
            out['time_remaining'] = max(0, SESSION_TIMEOUT - (now - out['stage_start']))
        else:
            out['time_remaining'] = 0

        if out['current_stage'] > 0:
            stage = STAGES[out['current_stage'] - 1]
            out['stage_name'] = stage['name']
            out['active_labs'] = [
                {'id': lab_id, 'user': f'lab{lab_id}', 'path': f'/lab/{lab_id}/',
                 **({'password': slots[lab_id]['password']} if include_creds else {})}
                for lab_id in stage['labs']
            ]
        else:
            out['active_labs'] = []
            out['stage_name'] = ''

    return out, 200


def do_admin_labs():
    """All lab slots and their current terminal passwords (admin only)."""
    with lock:
        return {'labs': [
            {'id': n, 'user': f'lab{n}', 'path': f'/lab/{n}/',
             'password': s['password'], 'owner': s['owner'],
             'attempt_id': s['attempt_id'], 'expires_at': s['expires_at'],
             'challenge_id': s['challenge_id']}
            for n, s in sorted(slots.items())
        ]}, 200


# ── Lease API auth (HMAC-SHA256) ───────────────────────────────────
def _prune_nonces(now):
    for k in [k for k, exp in _nonces.items() if exp < now]:
        _nonces.pop(k, None)


def verify_lease_auth(handler, body_bytes):
    """Verify X-CHX-* HMAC headers. Returns (ok, error_message)."""
    if not _lease_secret:
        return False, 'lease API is not configured (LEASE_SECRET unset)'

    ts = handler.headers.get('X-CHX-Timestamp', '')
    nonce = handler.headers.get('X-CHX-Nonce', '')
    sig = handler.headers.get('X-CHX-Signature', '')
    if not (ts and nonce and sig):
        return False, 'missing signature headers'
    if not re.match(r'^[A-Za-z0-9_-]{8,128}$', nonce):
        return False, 'bad nonce'

    try:
        ts_i = int(ts)
    except ValueError:
        return False, 'bad timestamp'

    now = int(time.time())
    if abs(now - ts_i) > CLOCK_SKEW_SECONDS:
        return False, 'timestamp outside allowed window'

    with lock:
        _prune_nonces(now)
        if nonce in _nonces:
            return False, 'nonce replayed'

    body_hash = hashlib.sha256(body_bytes or b'').hexdigest()
    path = handler.path.split('?')[0]
    payload = f'{handler.command}\n{path}\n{ts}\n{nonce}\n{body_hash}'.encode()
    expected = hmac.new(_lease_secret.encode(), payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, sig.strip().lower()):
        return False, 'bad signature'

    with lock:
        _nonces[nonce] = now + NONCE_TTL
    return True, None


# ── Lease API actions ──────────────────────────────────────────────
def lease_capacity():
    with lock:
        free = [n for n, s in slots.items() if s['owner'] is None]
        return {'total': MAX_LABS, 'free': len(free),
                'in_use': MAX_LABS - len(free),
                'free_slots': free}, 200


def lease_create(body):
    attempt_id = str(body.get('attempt_id') or '').strip()
    if not re.match(r'^[A-Za-z0-9_.:-]{1,128}$', attempt_id):
        return {'error': 'attempt_id is required (1-128 chars, [A-Za-z0-9_.:-])'}, 400

    try:
        duration = int(body.get('duration_seconds') or SESSION_TIMEOUT)
    except (TypeError, ValueError):
        return {'error': 'duration_seconds must be a number'}, 400
    if duration < 60 or duration > MAX_LEASE_SECONDS:
        return {'error': f'duration_seconds must be between 60 and {MAX_LEASE_SECONDS}'}, 400

    challenge_id = body.get('challenge_id')
    if challenge_id is not None:
        challenge_id = str(challenge_id).strip()
        if not CHALLENGE_ID_RE.match(challenge_id):
            return {'error': 'challenge_id must match ^[a-z0-9][a-z0-9_-]{0,47}$'}, 400

    now = int(time.time())

    with lock:
        # Idempotency: the same attempt_id returns its existing live lease.
        for n, s in slots.items():
            if s['owner'] == 'lease' and s['attempt_id'] == attempt_id and s['expires_at'] > now:
                return {'session_id': s['session_id'], 'lab_id': n,
                        'user': f'lab{n}', 'password': s['password'],
                        'terminal_path': f'/lab/{n}/', 'expires_at': s['expires_at'],
                        'remaining': s['expires_at'] - now,
                        'challenge_id': s['challenge_id'],
                        'flag_sha256': s['flag_sha256'], 'reused': True}, 200

        if exam['status'] == 'running':
            return {'error': 'lab is busy running the local demo exam'}, 503

        free = [n for n, s in slots.items() if s['owner'] is None]
        if not free:
            return {'error': 'no lab capacity available', 'retry_after': 60}, 503

        lab_num = free[0]
        session_id = secrets.token_urlsafe(24)
        password = new_password()
        expires_at = now + duration
        slots[lab_num].update({
            'owner': 'lease', 'session_id': session_id, 'attempt_id': attempt_id,
            'password': password, 'expires_at': expires_at,
            'challenge_id': challenge_id, 'flag_sha256': None, 'started_at': now,
        })
        sessions[session_id] = lab_num

    # Provision the challenge (and its per-attempt flag) before exposing the shell.
    flag_sha256 = None
    if challenge_id:
        # Hash exactly the string that gets planted — the learner submits the
        # whole CHX{...} token, so hashing the bare hex would never match.
        flag = f'CHX{{{secrets.token_hex(16)}}}'
        flag_sha256 = hashlib.sha256(flag.encode()).hexdigest()
        ok, err = provision_challenge(lab_num, challenge_id, flag)
        if not ok:
            release_lease(lab_num)
            return {'error': err}, 503
        with lock:
            slots[lab_num]['flag_sha256'] = flag_sha256

    if not start_ttyd(lab_num, password, end_time=expires_at):
        release_lease(lab_num)
        return {'error': 'failed to start terminal'}, 500

    print(f'[lease] Lab {lab_num} leased to attempt {attempt_id} for {duration}s')
    return {'session_id': session_id, 'lab_id': lab_num, 'user': f'lab{lab_num}',
            'password': password, 'terminal_path': f'/lab/{lab_num}/',
            'expires_at': expires_at, 'remaining': duration,
            'challenge_id': challenge_id, 'flag_sha256': flag_sha256,
            'reused': False}, 201


def lease_get(session_id):
    now = int(time.time())
    with lock:
        lab_num = sessions.get(session_id)
        if not lab_num:
            return {'error': 'session not found', 'status': 'ended'}, 404
        s = slots[lab_num]
        if s['owner'] != 'lease' or s['session_id'] != session_id:
            return {'error': 'session not found', 'status': 'ended'}, 404
        remaining = max(0, s['expires_at'] - now)
        return {'session_id': session_id, 'lab_id': lab_num, 'user': f'lab{lab_num}',
                'terminal_path': f'/lab/{lab_num}/', 'status': 'running' if remaining else 'expired',
                'expires_at': s['expires_at'], 'remaining': remaining,
                'attempt_id': s['attempt_id'], 'challenge_id': s['challenge_id'],
                'flag_sha256': s['flag_sha256']}, 200


def lease_delete(session_id):
    with lock:
        lab_num = sessions.get(session_id)
        if not lab_num or slots[lab_num]['session_id'] != session_id:
            return {'ok': True, 'already_ended': True}, 200
    release_lease(lab_num)
    print(f'[lease] Session {session_id[:8]}… released early')
    return {'ok': True, 'already_ended': False}, 200


# ── HTTP server ─────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'CyberHXLab'
    sys_version = ''

    def log_message(self, *_):
        pass

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            n = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return b''
        if n <= 0 or n > 64 * 1024:
            return b''
        return self.rfile.read(n)

    # X-CHX-Admin is set to "1" by nginx ONLY on routes behind auth_basic, and
    # explicitly cleared on every public route, so a client cannot forge it.
    # via_nginx() alone is not an authorisation signal: nginx attaches the
    # internal token to every proxied request, anonymous ones included.
    def _admin_ok(self):
        return via_nginx(self) and self.headers.get('X-CHX-Admin', '') == '1'

    def _lease_route(self, method, body=b''):
        ok, err = verify_lease_auth(self, body)
        if not ok:
            self._json({'error': err}, 401)
            return None
        return True

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/api/exam/status':
            data, code = do_status(include_creds=False)
            self._json(data, code)

        elif path == '/api/admin/labs':
            if not self._admin_ok():
                self._json({'error': 'forbidden'}, 403)
                return
            data, code = do_admin_labs()
            self._json(data, code)

        elif path == '/api/v1/capacity':
            if self._lease_route('GET') is None:
                return
            data, code = lease_capacity()
            self._json(data, code)

        elif path.startswith('/api/v1/sessions/'):
            if self._lease_route('GET') is None:
                return
            data, code = lease_get(path.rsplit('/', 1)[-1])
            self._json(data, code)

        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        path = self.path.split('?')[0]
        body = self._read_body()

        if path == '/api/exam/start':
            # Starting the demo consumes real capacity, so it is admin-gated
            # unless the operator opted in with PUBLIC_DEMO=true.
            if not PUBLIC_DEMO and not self._admin_ok():
                self._json({'error': 'This walkthrough is admin-only. Learners start '
                                     'their lab from the exam on pentestlab.cyberhx.com.'}, 403)
                return
            data, code = do_start()
            self._json(data, code)

        elif path == '/api/exam/reset':
            if not self._admin_ok():
                self._json({'error': 'forbidden'}, 403)
                return
            data, code = do_reset()
            self._json(data, code)

        elif path == '/api/v1/sessions':
            if self._lease_route('POST', body) is None:
                return
            try:
                payload = json.loads(body or b'{}')
                if not isinstance(payload, dict):
                    raise ValueError
            except Exception:
                self._json({'error': 'body must be a JSON object'}, 400)
                return
            data, code = lease_create(payload)
            self._json(data, code)

        else:
            self._json({'error': 'not found'}, 404)

    def do_DELETE(self):
        path = self.path.split('?')[0]
        if path.startswith('/api/v1/sessions/'):
            if self._lease_route('DELETE') is None:
                return
            data, code = lease_delete(path.rsplit('/', 1)[-1])
            self._json(data, code)
        else:
            self._json({'error': 'not found'}, 404)


# ── Main ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'[lab-api] Starting on :{API_PORT}')
    print(f'[lab-api] Slots: {MAX_LABS} | demo stage timeout: {SESSION_TIMEOUT}s')
    print(f'[lab-api] Internal token : {"loaded" if _api_token else "NOT SET (dev mode)"}')
    print(f'[lab-api] Lease API      : {"enabled" if _lease_secret else "DISABLED (set LEASE_SECRET)"}')
    print(f'[lab-api] Public demo    : {"OPEN to anyone" if PUBLIC_DEMO else "admin auth required"}')
    print(f'[lab-api] Challenge dir  : {CHALLENGE_DIR}')

    reaper = threading.Thread(target=reap_expired, daemon=True)
    reaper.start()

    srv = http.server.ThreadingHTTPServer(('127.0.0.1', API_PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('[lab-api] Shutting down')
        srv.shutdown()
