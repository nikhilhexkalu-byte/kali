# CyberHX Pentest Lab

Multi-user sandboxed Kali Linux lab with browser-based terminals. Built for security training on [Render](https://render.com) free plan.

## Features

- **10 isolated lab slots** — each user gets a separate terminal, user account and password
- **15-minute auto-expiry** — sessions are killed automatically after the timeout
- **Sandboxed network** — only `*.cyberhx.com` is reachable (enforced by proxy + iptables when available)
- **Admin dashboard** — see all credentials, copy/download CSV, monitor active sessions
- **Auto-recovery** — crashed labs restart automatically via watchdog
- **Single-port architecture** — Nginx reverse-proxies all 10 labs through Render's single `$PORT`

## Architecture

```
Internet ─► Render ($PORT)
             │
             ├─ Nginx reverse proxy
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
| `ADMIN_PASSWORD` | *random (see logs)* | Password for `/admin` panel |
| `MAX_LABS` | `10` | Number of lab slots (reduce for less RAM) |
| `SESSION_TIMEOUT` | `900` | Session timeout in seconds (900 = 15 min) |
| `ALLOWED_DOMAIN` | `cyberhx.com` | Whitelisted domain for sandbox |
| `LAB_1_PASSWORD` … `LAB_10_PASSWORD` | *random* | Fixed password for a specific lab |

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

1. **Tinyproxy** (always active) — HTTP/HTTPS whitelist proxy that only allows `*.cyberhx.com`
2. **iptables** (when available) — blocks all direct outbound traffic from lab users, forcing everything through the proxy

If the container lacks `NET_ADMIN` capability (common on free plans), only the proxy layer is active. Lab users' shells have `HTTP_PROXY`/`HTTPS_PROXY` pre-configured.

## Notes

- Containers on Render are ephemeral — files are lost on redeploy/restart
- Each lab user has passwordless `sudo` for tools that need root (e.g. `sudo nmap -sS`)
- Raw-socket scans may be limited; prefer `nmap -sT -Pn`
- Only test systems you own or have written permission to test
