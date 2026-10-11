# Lease API — connecting this lab to the exam site

This document is the contract between the lab (`vm.cyberhx.com`) and the
certification exam on `pentestlab.cyberhx.com`.

The rule that shapes everything: **a browser never talks to the lease API.**
Only the exam site's server does, signing each request with a shared secret.
Learners only ever receive a terminal URL and a password for the one slot
leased to their attempt.

---

## 1. Render environment variables

| Variable | Required | Default | What it does |
|---|---|---|---|
| `LEASE_SECRET` | **yes** | — | Shared secret. Must equal `LAB_LEASE_SECRET` on the exam site. Without it the lease API is disabled. |
| `ADMIN_PASSWORD` | **yes** | random each boot | Basic-auth password for `/admin` and `/api/exam/reset`. |
| `ALLOWED_FRAME_ANCESTORS` | for embedding | `'self'` | Who may embed the terminal. Set to `'self' https://pentestlab.cyberhx.com` to show it inside the exam page. |
| `PUBLIC_DEMO` | no | `false` | `true` lets anonymous visitors start the local demo exam. Leave `false` in production — the demo consumes real lab capacity. |
| `MAX_LABS` | no | `6` | Number of lab slots = maximum concurrent learners. |
| `MAX_LEASE_SECONDS` | no | `7200` | Upper bound on a single lease. |
| `SESSION_TIMEOUT` | no | `900` | Demo stage length, and the default lease length. |
| `CHALLENGE_DIR` | no | `/opt/challenges` | Where challenge provisioning scripts live. |
| `ALLOWED_DOMAIN` | no | `cyberhx.com` | Egress allowlist for lab users. |

Generate a secret with:

```bash
openssl rand -hex 32
```

Set the identical value as `LAB_LEASE_SECRET` in Vercel on the exam site.

---

## 2. Request signing

Every `/api/v1/*` request carries three headers:

```
X-CHX-Timestamp: <unix seconds>
X-CHX-Nonce:     <8-128 chars of [A-Za-z0-9_-], unique per request>
X-CHX-Signature: <lowercase hex HMAC-SHA256>
```

The signature is computed over five newline-separated fields:

```
METHOD \n PATH \n TIMESTAMP \n NONCE \n SHA256_HEX(BODY)
```

* `PATH` excludes the query string.
* `SHA256_HEX(BODY)` is the hex SHA-256 of the raw body; for an empty body use
  the hash of the empty string.

Rejections: `401` for a bad or missing signature, a timestamp more than
**300 seconds** from the lab's clock, or a nonce already seen inside that
window (replay protection).

Reference implementation (Node, matching the exam site):

```js
import crypto from 'crypto';

function sign(method, path, body, secret) {
  const ts = Math.floor(Date.now() / 1000).toString();
  const nonce = crypto.randomBytes(16).toString('hex');
  const bodyHash = crypto.createHash('sha256').update(body ?? '').digest('hex');
  const payload = `${method}\n${path}\n${ts}\n${nonce}\n${bodyHash}`;
  const sig = crypto.createHmac('sha256', secret).update(payload).digest('hex');
  return { 'X-CHX-Timestamp': ts, 'X-CHX-Nonce': nonce, 'X-CHX-Signature': sig };
}
```

---

## 3. Endpoints

### `POST /api/v1/sessions` — lease a lab

```json
{ "attempt_id": "uuid-of-the-exam-attempt",
  "duration_seconds": 3600,
  "challenge_id": "web-basic" }
```

`challenge_id` is optional. Omit it for a plain Kali shell with no target.

**201** on success:

```json
{ "session_id": "k7Jq…", "lab_id": 3, "user": "lab3",
  "password": "rotated-per-lease", "terminal_path": "/lab/3/",
  "expires_at": 1791748425, "remaining": 3600,
  "challenge_id": "web-basic",
  "flag_sha256": "9f86d08…", "reused": false }
```

* The password is **generated fresh for this lease** and dies with it.
* `flag_sha256` is the SHA-256 of the flag planted in the environment. The
  plaintext flag never leaves the lab. The site stores only this hash and
  compares it against what the learner submits.
* Calling again with the same `attempt_id` while the lease is live returns the
  same session with `"reused": true` — safe to retry, and safe on a page refresh.

Errors: `400` invalid input · `503` no free capacity (includes `retry_after`),
the demo exam is running, or challenge provisioning failed · `500` the terminal
failed to start. On any failure the slot is released, not left stranded.

### `GET /api/v1/sessions/{session_id}` — poll a lease

Returns `status`, `expires_at`, `remaining`, `attempt_id`, `challenge_id`,
`flag_sha256`. **Never returns the password** — the site already has it from
the create call. `404` once the lease has ended.

### `DELETE /api/v1/sessions/{session_id}` — end a lease early

Kills the terminal, kills the learner's processes, wipes their home directory,
runs the challenge teardown, and frees the slot. Idempotent.

### `GET /api/v1/capacity` — free slots

```json
{ "total": 6, "free": 4, "in_use": 2, "free_slots": [3, 4, 5, 6] }
```

Use this to tell a learner "all labs are busy" *before* they burn an attempt.

---

## 4. Lifecycle guarantees

* A lease expires on its own. A sweeper runs every 15 seconds and reclaims any
  slot past its deadline — the site does not have to call `DELETE`.
* Reclaiming a slot kills every process owned by that lab user, wipes the home
  directory back to a clean `.bashrc`/`.profile`, and runs `teardown.sh`.
* A slot is never shared. The demo exam and the lease API draw from one
  registry, so they cannot hand out the same lab.
* Lab users have no sudo, cannot read the nginx or proxy config, cannot see
  other processes (`hidepid=2`), and can only reach `*.cyberhx.com` on the
  network.

---

## 5. What is deliberately *not* here

* **No scoring.** The lab plants a flag and reports its hash. Deciding whether
  a learner passed is the exam site's job.
* **No learner accounts.** The lab has no idea who a learner is; it only knows
  an opaque `attempt_id`. Identity, payment and attempt limits stay on the site.
* **No challenge content.** See `CHALLENGES.md` — challenges are authored by
  the owner, not shipped here.
