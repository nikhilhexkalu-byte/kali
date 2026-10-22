#!/bin/bash
set -uo pipefail
pkill -f "challenge/${CHX_LAB_USER:-__none__}" 2>/dev/null || true
rm -rf "/srv/challenge/${CHX_LAB_USER:-__none__}" 2>/dev/null || true
exit 0
