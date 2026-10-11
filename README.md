# CyberHX Pentest Lab

Multi-user sandboxed Kali Linux lab with browser-based terminals. Built for security training on [Render](https://render.com) free plan.

Two ways in:

* **Lease API** (`/api/v1/*`) — how `pentestlab.cyberhx.com` leases one isolated
  lab slot per exam attempt. Server-to-server, HMAC-signed. See
  [INTEGRATION.md](INTEGRATION.md).
* **Demo walkthrough** (`/`) — the local staged exam used for testing. Behind
  admin login unless `PUBLIC_DEMO=true`.

> **No challenge ships in this image.** The six labs are identical Kali shells
> with no target and no flag. [CHALLENGES.md](CHALLENGES.md) documents the hook
> for adding your own.

## Features

- **4 isolated lab slots** (configurable up to 10) — each user gets a separate terminal, user account and password
- **15-minute auto-expiry** — sessions are killed automatically after the timeout
- **Sandboxed network** — only `*.cyberhx.com` is reachable (enforced by proxy + iptables when available)
- **Hardened security** — locked-down sudo, rate limiting, resource limits, audit logging
- **Admin dashboard** — see all credentials, copy/download CSV, monitor active sessions
- **Auto-recovery** — crashed labs restart automatically via watchdog
- **Single-port architecture** — Nginx reverse-proxies all labs through Render's single `$PORT`

## Architecture

```
Internet ─► Render ($PORT)
             │
             ├─ Nginx reverse proxy
             │    ├─ /api/v1/*   → Lease API     (HMAC, server-to-server)
             │    ├─ /           → Landing page  (public)
             │    ├─ /admin      → Admin panel   (password protected)
             │    ├─ /lab/1/     → ttyd :7681    (lab1 user, own password)
             │    ├─ /lab/2/     → ttyd :7682    (lab2 user, own password)
             │    └─ ...         → ttyd :768N    (labN user)
             │
             ├─ Tinyproxy :8888  (whitelist proxy → *.cyberhx.com only)
             └─ Session Manager  (kills sessions after 15 min)
```

## Deploy on Render

1. Push this repo to GitHub
2. Create a new **Web Service** on Render → connect this repo
3. Settings:
   - **Environment**: Docker
   - **Plan**: Free (or higher for more RAM)
   - **Health check path**: `/health`
4. Set environment variables (optional — all have sensible defaults):

| Variable | Default | Description |
|---|---|---|
| `ADMIN_PASSWORD` | *random (see admin panel)* | Password for `/admin` panel |
| `MAX_LABS` | `4` | Number of lab slots (up to 10, reduce for less RAM) |
| `SESSION_TIMEOUT` | `900` | Session timeout in seconds (900 = 15 min) |
| `ALLOWED_DOMAIN` | `cyberhx.com` | Whitelisted domain for sandbox |
| `LAB_1_PASSWORD` … `LAB_10_PASSWORD` | *random* | Starting password for a lab (leases rotate it per session) |
| `LEASE_SECRET` | *unset* | **Required for the exam integration.** Shared secret for `/api/v1/*`; must match `LAB_LEASE_SECRET` on the exam site. Unset = lease API disabled. |
| `ALLOWED_FRAME_ANCESTORS` | `'self'` | Who may embed the terminal. Use `'self' https://pentestlab.cyberhx.com` to show it inside the exam. |
| `PUBLIC_DEMO` | `false` | `true` lets anyone start the demo walkthrough and consume lab capacity. |
| `MAX_LEASE_SECONDS` | `7200` | Upper bound on one lease. |
| `CHALLENGE_DIR` | `/opt/challenges` | Where challenge provisioning scripts live. |

## URLs

| Path | Auth | Description |
|---|---|---|
| `/` | Public | Landing page with lab status |
| `/admin` | `admin:<ADMIN_PASSWORD>` | All credentials + status |
| `/lab/N/` | `labN:<password>` | Terminal for lab N |
| `/api/labs` | Public | Lab status JSON (no passwords) |
| `/api/admin/labs` | Admin | Full credentials JSON |
| `/health` | Public | Health check endpoint |

## Resource Usage (Render Free Plan)

- **RAM**: ~40 MB base + ~30 MB per active lab session
- **CPU**: Minimal (shells are mostly idle)
- **Tip**: Set `MAX_LABS=5` if you hit memory limits on the free plan

## Sandbox Details

Network restriction uses two layers:

1. **Tinyproxy** (always active) — HTTP/HTTPS whitelist proxy that only allows `*.cyberhx.com`. CONNECT method restricted to ports 443/563.
2. **iptables** (when available) — blocks all direct outbound traffic from lab users, forcing everything through the proxy

If the container lacks `NET_ADMIN` capability (common on free plans), only the proxy layer is active. Lab users' shells have `HTTP_PROXY`/`HTTPS_PROXY` pre-configured as `readonly` bash variables.

## Security Hardening

- **Sudo lockdown** — only `nmap` and `tcpdump` allowed (no blanket root access)
- **Resource limits** — `ulimit` restricts processes (50), file size (100MB), open files (256), memory (256MB)
- **Rate limiting** — nginx rate-limits admin/auth endpoints (5 req/min) to prevent brute-force
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- **Audit logging** — all lab user commands logged to `/var/log/lab-audit.log`
- **Credential protection** — passwords masked in logs, credential files root-only (chmod 600)
- **Home isolation** — user home directories set to `700` (no cross-user access)
- **Session protection** — session tracking files root-only, user-targeted process cleanup

## Notes

- Containers on Render are ephemeral — files are lost on redeploy/restart
- Each lab user has passwordless `sudo` only for `nmap` and `tcpdump` (raw socket tools)
- Raw-socket scans may be limited; prefer `nmap -sT -Pn`
- All commands are logged to `/var/log/lab-audit.log` for forensics
- Only test systems you own or have written permission to test
