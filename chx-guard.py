#!/usr/bin/env python3
"""Run a challenge's lab.py so its servers answer only the learner who owns this slot.

Every slot shares one container, and Render gives the container neither iptables
(no NET_ADMIN) nor hidepid. So any learner could reach any other slot's targets on
127.x. This wrapper closes that gap without privileges: before a server handles a
connection, it looks up which user opened the client socket (the uid column of
/proc/net/tcp, which every process can read) and only lets these in:

  * root (provisioning / health probes)
  * this service's own user (a challenge calling itself, e.g. Day 07's SSRF)
  * the slot's learner (CHX_LAB_USER), except on CHX_INTERNAL_PORTS, which are
    meant to be reachable only from the service itself.

Anyone else gets a short HTTP 403 and the connection is closed. A lookup that
fails is refused (fail closed).

Usage (as the service user): python3 chx-guard.py /srv/challenge/labN/lab.py
"""
import os
import pwd
import runpy
import socket
import socketserver
import struct
import sys


def _uid_of(name):
    try:
        return pwd.getpwnam(name).pw_uid
    except (KeyError, TypeError):
        return None


SERVICE_UID = os.getuid()
LAB_UID = _uid_of(os.environ.get('CHX_LAB_USER'))
INTERNAL_PORTS = {int(p) for p in os.environ.get('CHX_INTERNAL_PORTS', '').replace(',', ' ').split() if p.isdigit()}


def _hex_addr(ip, port):
    # /proc/net/tcp prints the IPv4 address as the host-order integer of the
    # network-order bytes, and the port as 4 hex digits.
    return '%08X:%04X' % (struct.unpack('=I', socket.inet_aton(ip))[0], port)


def peer_uid(sock):
    """uid that owns the client end of an accepted IPv4 loopback connection, or None."""
    try:
        peer_ip, peer_port = sock.getpeername()[:2]
        local_ip, local_port = sock.getsockname()[:2]
    except (OSError, ValueError):
        return None
    if not peer_ip.startswith('127.'):
        return None
    want_local, want_remote = _hex_addr(peer_ip, peer_port), _hex_addr(local_ip, local_port)
    try:
        with open('/proc/net/tcp') as f:
            next(f, None)
            for line in f:
                cols = line.split()
                if len(cols) > 7 and cols[1] == want_local and cols[2] == want_remote:
                    return int(cols[7])
    except OSError:
        return None
    return None


def allowed(uid, server_port):
    if uid is None:
        return False
    if uid in (0, SERVICE_UID):
        return True
    return LAB_UID is not None and uid == LAB_UID and server_port not in INTERNAL_PORTS


_REFUSED = (b'HTTP/1.0 403 Forbidden\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n'
            b'403: this service is not reachable from your session.\n')


def _verify_request(self, request, client_address):
    try:
        server_port = request.getsockname()[1]
    except OSError:
        return False
    if allowed(peer_uid(request), server_port):
        return True
    try:
        request.sendall(_REFUSED)
    except OSError:
        pass
    return False


socketserver.BaseServer.verify_request = _verify_request

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('usage: chx-guard.py <lab.py> [args...]')
    target = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(target, run_name='__main__')
