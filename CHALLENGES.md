# Authoring a lab challenge

Right now this image ships **no challenge**: all six labs are identical Kali
shells with no target to attack and nothing to find. The stage names
(Reconnaissance / Exploitation / Post-Exploitation) are labels only.

That is fine for a guided walkthrough, but a certification practical needs a
real target and a flag that proves the learner reached it. This file explains
the hook that makes that possible. **You write the challenge** — it is exam
content, the same as your exam questions.

---

## How it fits together

1. The exam site leases a lab with `"challenge_id": "web-basic"`.
2. The lab generates a random flag, formatted `CHX{<32 hex chars>}`.
3. The lab runs `/opt/challenges/web-basic/provision.sh` with the flag in the
   environment. Your script stands up the target and hides the flag where only
   a successful attack reveals it.
4. The lab returns **only the SHA-256 of the flag** to the site.
5. The learner attacks the target, finds the flag, pastes it into the exam.
6. The site hashes what they typed and compares. The plaintext flag never
   leaves the lab, and never touches the learner's browser from our side.

Because the flag is regenerated per attempt, one learner cannot pass another
learner a working flag.

---

## Layout

```
/opt/challenges/
  web-basic/
    provision.sh     # required, executable
    teardown.sh      # optional, executable
    README.md        # notes for you
```

Add them in the `Dockerfile`:

```dockerfile
COPY challenges/ /opt/challenges/
RUN chmod -R 700 /opt/challenges && chmod +x /opt/challenges/*/*.sh
```

A `challenge_id` must match `^[a-z0-9][a-z0-9_-]{0,47}$`. Anything else is
rejected before a script is looked up, and the resolved path is checked to stay
inside `CHALLENGE_DIR`.

---

## What your scripts receive

| Variable | Example | Meaning |
|---|---|---|
| `CHX_FLAG` | `CHX{a1b2…}` | The flag to plant. Different every lease. |
| `CHX_LAB_NUM` | `3` | Which slot is being provisioned. |
| `CHX_LAB_USER` | `lab3` | The learner's unix user. |
| `CHX_LAB_HOME` | `/home/lab3` | That user's home directory. |

`provision.sh` must exit `0`. A non-zero exit or longer than 120 seconds fails
the lease, the slot is released, and the site is told the lab is unavailable —
so the learner is never charged an attempt for your script breaking.

`teardown.sh` runs when the lease ends. It gets the same variables except
`CHX_FLAG`. Keep it quick (60 second cap) and make it safe to run twice.

---

## Example skeleton

```bash
#!/bin/bash
# /opt/challenges/web-basic/provision.sh
set -euo pipefail

PORT=$((8000 + CHX_LAB_NUM))
ROOT="/srv/challenge/${CHX_LAB_USER}"

rm -rf "$ROOT"; mkdir -p "$ROOT"

# ── Plant the flag where only a successful attack reaches it ──────
# Do NOT put it anywhere $CHX_LAB_USER can simply read.
install -o root -g root -m 600 /dev/null "$ROOT/flag.txt"
printf '%s\n' "$CHX_FLAG" > "$ROOT/flag.txt"

# ── Stand up your vulnerable service, bound to localhost ──────────
# (your target goes here — it must listen on 127.0.0.1 only)

echo "provisioned ${CHX_LAB_USER} on :${PORT}"
```

```bash
#!/bin/bash
# /opt/challenges/web-basic/teardown.sh
set -uo pipefail
pkill -f "challenge/${CHX_LAB_USER}" 2>/dev/null || true
rm -rf "/srv/challenge/${CHX_LAB_USER}" 2>/dev/null || true
exit 0
```

---

## Rules worth keeping

* **Bind targets to `127.0.0.1`.** Egress is already restricted to
  `*.cyberhx.com`, and a target on a public port would be reachable by anyone.
* **Never let the flag be readable without the attack.** If `cat` finds it,
  the practical proves nothing. Root-owned `0600` files, a database row behind
  an injection, or a file only the escalated user can read all work.
* **One target per lab slot.** Slots run side by side in one container, so
  derive ports and paths from `CHX_LAB_NUM` as above or learners will collide.
* **Make it finishable.** The lease length is set by the exam site. Size the
  challenge for well under that, or nobody passes.
* **Test both scripts twice in a row.** Teardown then provision again must
  leave a clean target — slots get reused all day.

### Permissions: the candidate's own account gets nothing

`CHX_LAB_USER` is the account the candidate's terminal runs as. It must have **no**
filesystem path into the challenge — the exam is the chain, and anything the
candidate can simply read or execute is a shortcut around it:

- Own `/srv/challenge/<user>` and everything in it `root` or the per-slot service
  user, never `CHX_LAB_USER`, and never put `CHX_LAB_USER` in the service user's
  group (or the service user in the candidate's group).
- A SUID helper must be mode `4750` owned `root:<service-user>`, so only a shell
  obtained through the challenge can run it. `4750 root:<candidate>` hands over
  root in one command.
- The challenge source and its database are the answer key (credentials, record
  counts, versions). Keep them `640`/`600` away from the candidate's group.
- `chown` clears the SUID bit, so always `chown` before `chmod 4750`.
- Verify it: as `CHX_LAB_USER`, `ls`, `cat` the source, read the database and run
  the SUID helper. Every one of those must fail. Then, as the service user, run
  the helper and read the flag — that must succeed.
