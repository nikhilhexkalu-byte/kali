#!/bin/bash
# Creates a Parrot OS-styled .bashrc for each lab user
# Also saves a clean copy at /etc/cyberhx/clean-bashrc for restoration
# after a slot is wiped between students.
mkdir -p /etc/cyberhx
for i in $(seq 1 10); do
  cat > "/home/lab${i}/.bashrc" <<'BASHRC'
# ── Parrot OS style prompt ─────────────────────────────────
export PS1='\[\e[01;32m\]┌──(\[\e[1;36m\]\u㉿cyberhx\[\e[01;32m\])-[\[\e[0;1m\]\w\[\e[01;32m\]]\n\[\e[01;32m\]└─\[\e[1;36m\]\$\[\e[0m\] '

alias ll='ls -lah --color=auto'
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias ip='ip --color=auto'
alias diff='diff --color=auto'

# ── Audit logging (uses bash builtins only — no forks) ──────
export PROMPT_COMMAND='history -a; printf "%(%Y-%m-%d %H:%M:%S)T [%s] %s\n" -1 "$USER" "$(history 1)" >> /var/log/lab-audit.log 2>/dev/null'
export HISTTIMEFORMAT="%F %T  "
export HISTSIZE=1000
export HISTFILESIZE=1000
shopt -s histappend 2>/dev/null

# Sandbox proxy – only *.cyberhx.com reachable
# Marked readonly so users can't simply `unset` them
export http_proxy="http://127.0.0.1:8888"
export https_proxy="http://127.0.0.1:8888"
export HTTP_PROXY="http://127.0.0.1:8888"
export HTTPS_PROXY="http://127.0.0.1:8888"
export no_proxy="localhost,127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,::1"
export NO_PROXY="$no_proxy"
readonly http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY 2>/dev/null

clear
_lab_num="${USER#lab}"
_end_file="/tmp/.lab-end-time-${_lab_num}"
if [ -f "$_end_file" ] 2>/dev/null; then
  _end=$(cat "$_end_file" 2>/dev/null || echo 0)
  _left=$(( _end - $(date +%s) ))
  [ "$_left" -lt 0 ] && _left=0
  _h=$(( _left / 3600 )); _m=$(( (_left % 3600) / 60 ))
  if [ "$_h" -gt 0 ]; then _time="${_h}h ${_m}m remaining"
  else _time="${_m}m remaining"; fi
else
  _time="${SESSION_TIMEOUT:-3600}s session"
fi
echo ""
echo -e "  \e[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m"
echo -e "   \e[1;36mCYBERHX\e[0m \e[0;90m//\e[0m \e[0;37mPentestLab\e[0m"
echo -e "  \e[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m"
echo -e "   \e[0;90mSession\e[0m \e[0;36m:\e[0m \e[0;33m${_time}\e[0m"
echo -e "   \e[0;90mNetwork\e[0m \e[0;36m:\e[0m \e[0;33msandboxed · *.cyberhx.com\e[0m"
echo -e "   \e[0;90mTools\e[0m   \e[0;36m:\e[0m \e[0;37mnmap, nikto, sqlmap, hydra, gobuster\e[0m"
echo -e "  \e[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\e[0m"
echo -e "   \e[0;90mOnly test systems you have permission for.\e[0m"
echo ""
unset _lab_num _end_file _end _left _h _m _time
BASHRC
  chown "lab${i}:lab${i}" "/home/lab${i}/.bashrc"
  [ "$i" -eq 1 ] && cp "/home/lab1/.bashrc" /etc/cyberhx/clean-bashrc
done
chmod 600 /etc/cyberhx/clean-bashrc
