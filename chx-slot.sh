#!/bin/bash
# /usr/local/lib/chx/chx-slot.sh — helpers sourced by challenge provision.sh scripts (run as root).
#
# Each slot N owns the TCP block 8100+(N-1)*10 … +9. Learners share one container,
# so any of them could bind another slot's port while it is idle and pose as its
# target. chx_free_block clears the block before a service starts, and
# chx_wait_listen only accepts the port once it is held by the slot's service user.

chx_block_base() { echo $((8100 + (${1:?lab number} - 1) * 10)); }

# Kill whatever listens on the slot's ports (any owner), then wait until they are free.
chx_free_block() {
  local base="${1:?base port}" p pid i
  for p in $(seq "$base" $((base + 9))); do
    for pid in $(ss -Htlnp "sport = :$p" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
      kill -9 "$pid" 2>/dev/null || true
    done
  done
  for i in $(seq 1 25); do
    ss -Htln "( sport >= :$base and sport <= :$((base + 9)) )" 2>/dev/null | grep -q . || return 0
    sleep 0.2
  done
  return 0
}

# Succeed once PORT is listened on by a process owned by USER (up to ~8 s).
chx_wait_listen() {
  local port="${1:?port}" user="${2:?user}" uid pid i
  uid="$(id -u "$user" 2>/dev/null)" || return 1
  for i in $(seq 1 40); do
    for pid in $(ss -Htlnp "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
      [ "$(stat -c %u "/proc/$pid" 2>/dev/null)" = "$uid" ] && return 0
    done
    sleep 0.2
  done
  return 1
}

# Root-only log file for a slot's service (never in world-readable /tmp).
chx_log_path() {
  install -d -m 700 /var/log/chx
  echo "/var/log/chx/lab-${1:?lab number}.log"
}
