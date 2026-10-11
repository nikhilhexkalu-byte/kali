#!/bin/bash
# Creates a branded .bashrc for each lab user
for i in $(seq 1 10); do
  cat > "/home/lab${i}/.bashrc" <<'BASHRC'
export PS1='\[\e[1;36m\]┌──[\[\e[1;32m\]\u@cyberhx-lab\[\e[1;36m\]]-[\[\e[1;34m\]\w\[\e[1;36m\]]\n\[\e[1;36m\]└─\[\e[1;31m\]$ \[\e[0m\]'
alias ll='ls -lah --color=auto'
alias ls='ls --color=auto'
alias grep='grep --color=auto'

# ── Audit logging (uses bash builtins only — no forks) ────────
export PROMPT_COMMAND='printf "%(%Y-%m-%d %H:%M:%S)T [%s] %s\n" -1 "$USER" "$(history 1)" >> /var/log/lab-audit.log 2>/dev/null'
export HISTTIMEFORMAT="%F %T  "
export HISTSIZE=500
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
echo ""
echo -e "\e[1;36m╔════════════════════════════════════════════════════════════╗"
echo -e "║\e[0m                                                          \e[1;36m║"
echo -e "║\e[1;32m   ██████╗██╗   ██╗██████╗ ███████╗██████╗ ██╗  ██╗██╗  ██╗\e[1;36m║"
echo -e "║\e[1;32m  ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██║  ██║╚██╗██╔╝\e[1;36m║"
echo -e "║\e[1;32m  ██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝███████║ ╚███╔╝ \e[1;36m║"
echo -e "║\e[1;32m  ██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗██╔══██║ ██╔██╗ \e[1;36m║"
echo -e "║\e[1;32m  ╚██████╗   ██║   ██████╔╝███████╗██║  ██║██║  ██║██╔╝ ██╗\e[1;36m║"
echo -e "║\e[1;32m   ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝\e[1;36m║"
echo -e "║\e[0m                                                          \e[1;36m║"
echo -e "║\e[1;33m              ⚡ Pentest Lab — Kali Linux ⚡              \e[1;36m║"
echo -e "║\e[0m                                                          \e[1;36m║"
echo -e "║  \e[1;37m⏱  Session timeout : \e[1;31m15 minutes\e[0m                          \e[1;36m║"
echo -e "║  \e[1;37m🔒 Sandbox mode    : \e[1;31mONLY *.cyberhx.com\e[0m                  \e[1;36m║"
echo -e "║  \e[1;37m🛡  Privilege       : \e[1;33msudo nmap/tcpdump only\e[0m              \e[1;36m║"
echo -e "║\e[0m                                                          \e[1;36m║"
echo -e "║  \e[0;90mOnly scan systems you own or have written permission.\e[0m   \e[1;36m║"
echo -e "╚════════════════════════════════════════════════════════════╝\e[0m"
echo ""
BASHRC
  chown "lab${i}:lab${i}" "/home/lab${i}/.bashrc"
done
