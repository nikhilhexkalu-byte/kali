#!/usr/bin/env python3
"""CAPT Day 11: Privilege Escalation — web shell with simulated SUID."""
import http.server, os, subprocess, html
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie

FLAG = os.environ.get('CHX_FLAG', 'CHX{default}')
PORT = int(os.environ.get('SVC_PORT', '8080'))

FILESYSTEM = {
    '/etc/passwd': 'root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin\nwww-data:x:33:33:www-data:/var/www\nstudent:x:1000:1000::/home/student:/bin/bash',
    '/etc/shadow': 'Permission denied',
    '/home/student/.bash_history': 'ls -la\nfind / -perm -4000 2>/dev/null\n./finder /root -name flag.txt\n',
    '/usr/local/bin/finder': '[SUID binary — acts like find command, runs as root]',
    '/root/flag.txt': FLAG,
    '/tmp/notes.txt': 'TODO: remove the SUID bit from /usr/local/bin/finder',
}
SUID_BINS = ['-rwsr-xr-x 1 root root 42K /usr/local/bin/finder']

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = self.path.split('?')[0].rstrip('/') or '/'
        cookie = SimpleCookie(self.headers.get('Cookie',''))
        if p == '/':
            self._html('<h1>Lab Server — SSH Simulator</h1><form method="POST" action="/login"><input name="user" value="student"><input name="pass" type="password" placeholder="Password"><button>Login</button></form><p>Creds: student / student123</p>')
        elif p == '/shell':
            if not (cookie.get('auth') and cookie['auth'].value == 'student'):
                self.send_response(302); self.send_header('Location','/'); self.end_headers(); return
            self._html('<h1>Web Shell</h1><p>student@lab:~$</p><form method="POST" action="/shell"><input name="cmd" placeholder="Enter command" style="width:500px;font-family:monospace" autofocus><button>Run</button></form><pre>Type commands: ls, cat, find, id, whoami, pwd</pre>')
        else:
            self.send_response(404); self.end_headers(); self.wfile.write(b'404')
    def do_POST(self):
        ln = int(self.headers.get('Content-Length', 0))
        body = parse_qs(self.rfile.read(ln).decode())
        p = self.path.split('?')[0]
        if p == '/login':
            u, pw = body.get('user',[''])[0], body.get('pass',[''])[0]
            if u == 'student' and pw == 'student123':
                self.send_response(302); self.send_header('Set-Cookie','auth=student; Path=/'); self.send_header('Location','/shell'); self.end_headers()
            else:
                self._html('<h1>Login Failed</h1><a href="/">Retry</a>')
        elif p == '/shell':
            cmd = body.get('cmd',[''])[0].strip()
            output = self._exec(cmd)
            self._html(f'<h1>Web Shell</h1><p>student@lab:~$</p><form method="POST"><input name="cmd" value="" style="width:500px;font-family:monospace" autofocus><button>Run</button></form><pre>$ {html.escape(cmd)}\n{html.escape(output)}</pre>')
        else:
            self.send_response(404); self.end_headers()
    def _exec(self, cmd):
        parts = cmd.split()
        if not parts: return ''
        c = parts[0]
        if c == 'id': return 'uid=1000(student) gid=1000(student) groups=1000(student)'
        if c == 'whoami': return 'student'
        if c == 'pwd': return '/home/student'
        if c == 'ls':
            if '-la' in cmd and '/root' in cmd: return 'ls: cannot open directory /root: Permission denied'
            return 'Desktop  Documents  Downloads  .bash_history'
        if c == 'cat':
            target = parts[1] if len(parts) > 1 else ''
            if target in FILESYSTEM:
                if target == '/root/flag.txt': return 'cat: /root/flag.txt: Permission denied'
                return FILESYSTEM[target]
            return f'cat: {target}: No such file or directory'
        if c == 'find':
            if '-perm' in cmd and '-4000' in cmd:
                return '\n'.join(['/usr/local/bin/finder']) + '\n'
            if '-name' in cmd and 'flag' in cmd:
                return '/root/flag.txt\n'
            return ''
        if c == 'finder' or c == './finder' or c == '/usr/local/bin/finder':
            # Simulated SUID binary — runs as root
            if '-exec' in cmd:
                exec_idx = parts.index('-exec')
                exec_cmd = ' '.join(parts[exec_idx+1:]).replace('{}','found_file').rstrip(';').strip()
                if 'cat' in exec_cmd and 'flag' in cmd:
                    return FLAG
                return f'(executed: {exec_cmd})'
            target = parts[1] if len(parts) > 1 else '.'
            if 'flag' in cmd: return '/root/flag.txt'
            return '(finder output)'
        if c == 'file':
            if 'finder' in cmd: return '/usr/local/bin/finder: setuid ELF 64-bit LSB executable'
            return 'data'
        return f'{c}: command not found'
    def _html(self, b):
        self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b.encode())

if __name__ == '__main__':
    http.server.HTTPServer(('0.0.0.0', PORT), H).serve_forever()
