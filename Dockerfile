FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=xterm-256color \
    LANG=C.UTF-8 \
    TZ=Asia/Kolkata \
    MAX_LABS=6 \
    SESSION_TIMEOUT=900 \
    ALLOWED_DOMAIN=cyberhx.com

# ── Core tools + lab infrastructure ──────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        # essentials
        ca-certificates curl wget git sudo vim nano tmux htop unzip less procps \
        openssh-client iproute2 jq \
        # python
        python3 python3-pip python3-venv \
        # networking / recon
        net-tools iputils-ping traceroute dnsutils whois netcat-openbsd \
        nmap nikto sqlmap hydra john dirb gobuster whatweb wordlists \
        # lab infrastructure
        ttyd nginx-light tinyproxy iptables \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ( [ -f /usr/share/wordlists/rockyou.txt.gz ] && gunzip -kf /usr/share/wordlists/rockyou.txt.gz || true )

# ── Create lab users (lab1 … lab10) ──────────────────────────────
# Create lab users — no sudo at all (nmap/tcpdump get cap_net_raw via setcap).
RUN apt-get update && apt-get install -y --no-install-recommends libcap2-bin \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && for i in $(seq 1 10); do \
        useradd -m -s /bin/bash "lab${i}" && \
        chmod 700 "/home/lab${i}" ; \
    done \
    && setcap cap_net_raw+ep /usr/bin/nmap 2>/dev/null || true \
    && setcap cap_net_raw+ep /usr/sbin/tcpdump 2>/dev/null || true

# ── Per-user shell config (prompt, proxy, banner) ────────────────
COPY setup-bashrc.sh /tmp/setup-bashrc.sh
RUN chmod +x /tmp/setup-bashrc.sh && /tmp/setup-bashrc.sh && rm /tmp/setup-bashrc.sh

# ── Copy lab scripts & configs ───────────────────────────────────
COPY start.sh            /start.sh
COPY session-manager.sh  /session-manager.sh
COPY exam-api.py         /exam-api.py
COPY lab-shell.sh        /usr/local/bin/lab-shell.sh
COPY nginx.conf.template /etc/nginx/nginx.conf.template
COPY tinyproxy.conf      /etc/tinyproxy/tinyproxy.conf
COPY filter.txt          /etc/tinyproxy/filter.txt
COPY landing/            /var/www/landing/

RUN sed -i 's/\r$//' /start.sh /session-manager.sh /usr/local/bin/lab-shell.sh /exam-api.py \
    && chmod +x /start.sh /session-manager.sh /usr/local/bin/lab-shell.sh /exam-api.py \
    && touch /var/log/lab-audit.log && chmod 622 /var/log/lab-audit.log

WORKDIR /home

# Render injects $PORT at runtime
EXPOSE 10000

CMD ["/start.sh"]
