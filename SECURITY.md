# Security

Custom Lab LIMS Web is a **local-first** research tool. It is **not** hardened as a public multi-tenant SaaS.

## Default posture

- Bind to **`127.0.0.1`** (loopback) via `run.sh` / `run.bat` / README examples.
- Do **not** publish the port to the internet by default.
- Sessions use Starlette `SessionMiddleware` with a secret stored in `data/.session_secret` (gitignored).
- Passwords are hashed with Werkzeug (not stored in plaintext).

## What is gitignored

- `*.db`, `data/labs/`, `data/labs_registry.json`, `data/.session_secret`
- `uploads/**` (except `.gitkeep`)
- `.env`, virtualenvs

Never commit real patient/clinical data, API keys, or production secrets.

## Uploads

- Filenames are sanitized; path components are stripped.
- Structure files are written only under `uploads/structures/`.
- Reads of stored structure paths must resolve under that directory (traversal rejected).

## Per-lab isolation

- Each lab uses a separate SQLite file under `data/labs/<CODE>/`.
- Switching labs clears the browser session to reduce cross-lab credential leakage.
- Users are **not** copied when creating a new empty lab.

## Optional HTTPS

If you must expose beyond loopback (LAN demo, reverse proxy):

1. Terminate TLS at a reverse proxy (Caddy, nginx, Traefik) or use a tunnel with auth.
2. Keep the app on loopback; proxy to `127.0.0.1:8000`.
3. Prefer short-lived sessions, strong admin passwords, and OS firewall rules.
4. Example (Caddy conceptual):

```
lims.example.local {
  reverse_proxy 127.0.0.1:8000
}
```

Uvicorn can serve TLS directly (`--ssl-keyfile` / `--ssl-certfile`) for lab demos, but a proxy is usually cleaner.

## Reporting

This is a portfolio/educational project. For issues in your fork, open a GitHub issue on your repository. Do not file PHI or credentials in tickets.
