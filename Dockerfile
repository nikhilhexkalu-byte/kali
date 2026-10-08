FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=xterm-256color \
    LANG=C.UTF-8 \
    TZ=Asia/Kolkata

# Core pentest lab tools. Heavy suites (metasploit-framework, kali-tools-web) are
# intentionally left out so the image builds and runs on small Render plans.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl wget git sudo vim nano tmux htop unzip less procps \
        openssh-client iproute2 \
        python3 python3-pip python3-venv \
        net-tools iputils-ping traceroute dnsutils whois netcat-openbsd \
        nmap nikto sqlmap hydra john dirb gobuster whatweb wordlists \
        ttyd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ( [ -f /usr/share/wordlists/rockyou.txt.gz ] && gunzip -kf /usr/share/wordlists/rockyou.txt.gz || true )

# Nicer shell
RUN printf '%s\n' \
      "export PS1='\\[\\e[1;32m\\]\\u@pentestlab\\[\\e[0m\\]:\\[\\e[1;34m\\]\\w\\[\\e[0m\\]# '" \
      "alias ll='ls -lah --color=auto'" \
      "alias ls='ls --color=auto'" \
      "echo 'PentestLab ready. Scan only systems you own or are authorised to test.'" \
      >> /root/.bashrc

COPY start.sh /start.sh
# strip Windows line endings (if any) and make executable
RUN sed -i 's/\r$//' /start.sh && chmod +x /start.sh

WORKDIR /root

# Render injects $PORT at runtime; start.sh listens on it
EXPOSE 10000

CMD ["/start.sh"]
