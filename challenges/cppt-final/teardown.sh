#!/bin/bash
# /opt/challenges/cppt-final/teardown.sh
set -uo pipefail
pkill -f "challenge/${CHX_LAB_USER}/server.py" 2>/dev/null || true
userdel "www-chx${CHX_LAB_NUM}" 2>/dev/null || true
rm -rf "/srv/challenge/${CHX_LAB_USER}" 2>/dev/null || true
exit 0
