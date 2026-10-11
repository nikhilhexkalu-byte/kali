#!/bin/bash
# Creates a Kali-styled .bashrc for each lab user
for i in $(seq 1 10); do
  cat > "/home/lab${i}/.bashrc" <<'BASHRC'
# ── Kali Linux style prompt ─────────────────────────────────
# Matches the default Kali 2024 two-line prompt
export PS1='\[\e[01;32m\]┌──(\[\e[1;34m\]\u㉿cyberhx\[\e[01;32m\])-[\[\e[0;1m\]\w\[\e[01;32m\]]\n\[\e[01;32m\]└─\[\e[1;34m\]\$\[\e[0m\] '

alias ll='ls -lah --color=auto'
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias ip='ip --color=auto'
alias diff='diff --color=auto'

# ── Audit logging (uses bash builtins only — no forks) ──────
export PROMPT_COMMAND='printf "%(%Y-%m-%d %H:%M:%S)T [%s] %s\n" -1 "$USER" "$(history 1)" >> /var/log/lab-audit.log 2>/dev/null'
export HISTTIMEFORMAT="%F %T  "
export HISTSIZE=1000
export HISTFILESIZE=0
shopt -s histappend 2>/dev/null

# Sandbox proxy – only *.cyberhx.com reachable
# Marked readonly so users can't simply `unset` them
export http_proxy="http://127.0.0.1:8888"
export https_proxy="http://127.0.0.1:8888"
export HTTP_PROXY="http://127.0.0.1:8888"
export HTTPS_PROXY="http://127.0.0.1:8888"
export no_proxy="localhost,127.0.0.1"
readonly http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy 2>/dev/null

clear
cat << 'EOF'

   ╔══════════════════════════════════════════════════════════════╗
   ║                                                              ║
EOF
echo -e "   ║  \e[1;34m   ██████ \e[1;37m██   ██ \e[1;34m██████  \e[1;37m███████ \e[1;34m██████  \e[1;37m██   ██ \e[1;34m██   ██\e[0m  ║"
echo -e "   ║  \e[1;34m  ██      \e[1;37m ██ ██  \e[1;34m██   ██ \e[1;37m██      \e[1;34m██   ██ \e[1;37m██   ██ \e[1;34m ██ ██\e[0m   ║"
echo -e "   ║  \e[1;34m  ██      \e[1;37m  ███   \e[1;34m██████  \e[1;37m█████   \e[1;34m██████  \e[1;37m███████ \e[1;34m  ███\e[0m    ║"
echo -e "   ║  \e[1;34m  ██      \e[1;37m ██ ██  \e[1;34m██   ██ \e[1;37m██      \e[1;34m██   ██ \e[1;37m██   ██ \e[1;34m ██ ██\e[0m   ║"
echo -e "   ║  \e[1;34m   ██████ \e[1;37m██   ██ \e[1;34m██████  \e[1;37m███████ \e[1;34m██   ██ \e[1;37m██   ██ \e[1;34m██   ██\e[0m  ║"
echo -e "   ║                                                              ║"
echo -e "   ║        \e[1;37m  Pentest Training Lab — Kali Linux  \e[0m          ║"
echo -e "   ║                                                              ║"
echo -e "   ║  \e[0;32m Session  \e[0m: \e[1;31m15 min timeout\e[0m                                ║"
echo -e "   ║  \e[0;32m Network  \e[0m: \e[1;33msandboxed — only *.cyberhx.com\e[0m               ║"
echo -e "   ║  \e[0;32m Sudo     \e[0m: \e[1;33mnmap, tcpdump\e[0m                                ║"
echo -e "   ║                                                              ║"
echo -e "   ║  \e[0;90mOnly test systems you own or have written permission.\e[0m     ║"
cat << 'EOF'
   ╚══════════════════════════════════════════════════════════════╝

EOF
BASHRC
  chown "lab${i}:lab${i}" "/home/lab${i}/.bashrc"
done
