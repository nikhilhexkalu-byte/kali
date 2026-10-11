#!/bin/bash
# Wrapper: forces --unprivileged mode on Render (no raw sockets).
# Falls back to TCP connect scans (-sT) automatically.
exec /usr/bin/nmap --unprivileged "$@"
