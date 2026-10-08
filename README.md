# PentestLab (Kali Linux web terminal on Render)

Kali Linux container with a browser-based terminal ([ttyd](https://github.com/tsl0922/ttyd)) for pentesting course labs.

## Environment variables (Render > Environment)

| Key | Meaning |
| --- | --- |
| `TERMINAL_PASSWORD` | Login password (if unset, a random one is printed in the service logs) |
| `TERMINAL_USER` | Login username (default `kali`) |

## Use

- Open `https://<your-service>.onrender.com` (or your custom domain) and log in with the basic-auth prompt.
- You land in a shared `tmux` session named `main`; it survives browser refreshes.
- Command line access to the same terminal: `https://USER:PASSWORD@<host>/` in a browser. ttyd speaks WebSocket, so it is not a REST API.

## Notes

- Containers on Render are ephemeral: files are lost on redeploy/restart unless you attach a paid disk.
- Raw-socket scans may be limited in containers. Prefer `nmap -sT -Pn <target>` (TCP connect scan).
- Only test systems you own or have written permission to test.
