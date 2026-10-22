#!/bin/bash
# /opt/challenges/capt-basic/teardown.sh
set -uo pipefail
pkill -f "challenge/lab${CHX_LAB_NUM:-0}" 2>/dev/null || true
rm -rf "/srv/challenge/${CHX_LAB_USER:-__none__}" 2>/dev/null || true
exit 0
