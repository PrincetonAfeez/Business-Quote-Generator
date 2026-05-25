# Business Quote Generator

A Django 5 quote workflow app for small service businesses. It supports client and catalog management, per-user quotes, HTMX-driven line-item editing, public quote links, accept/decline tracking, email sending, and on-demand PDF export.

## Stack

- **Python 3.12.7** — pinned in `runtime.txt` for Railway deployment
- **Python 3.12 and 3.14** — tested locally and in GitHub Actions (`.github/workflows/tests.yml`)
- Django 5.1
- Django templates, HTMX, Tailwind CSS
- SQLite for development
- PostgreSQL on Railway
- Pillow for company logos
- ReportLab for PDFs
- WhiteNoise for production static files
- gunicorn for production WSGI

## Features mapped to grading

- **Auth & ownership**: signup, login, logout, password reset; every model is owner-scoped and access is enforced by an `OwnedManager`.
- **CRUD**: clients, catalog items, quotes, and quote line items, each with HTMX inline editing.
- **State machine**: explicit `TRANSITIONS` table on `Quote` with lazy expiry, invalid-transition rejection, and locked editing once a quote leaves `Draft`.
- **Money safety**: every monetary value is `Decimal`, rounded with `ROUND_HALF_UP`, and totals are recomputed server-side after every mutation (single source of truth — see `ADR-0002`).
- **Per-user, per-year quote numbering** with a `select_for_update()` counter inside an atomic transaction.
- **Public quote flow**: token-gated `/q/<token>/` URL, `Sent → Viewed` on first non-bot GET, Accept/Decline buttons, IP/UA audit, revocable from the owner UI.
- **PDF export**: ReportLab, branded header with logo, status pill, line item table with unit, totals, terms/notes; HTML-escaped to defend against ReportLab markup injection.
- **HTMX showcase**: `innerHTML`, `outerHTML`, `beforeend`, `none`, `hx-swap-oob`, `hx-include`, and `HX-Trigger` toasts — see [docs/htmx-patterns.md](docs/htmx-patterns.md).
- **Content negotiation**: HTML, partial HTML, and JSON on the same URLs.
- **Validation**: model `clean()` enforces discount, expiry, and flat-discount-vs-subtotal rules; field validators reject negative tax rates and out-of-range values.
- **Test suite**: 83 tests covering ownership, money math, transitions, HTMX responses, content negotiation, PDF smoke, failure paths, and deployment config.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata quotes/fixtures/seed.json
python manage.py runserver
```

The seed account is `demo` with password `demo12345`. **This account is for local demo and grading only — never load this fixture into production.**

## Environment variables

Set these in `.env` locally and in Railway's dashboard for production:

- `SECRET_KEY` — required in production (no default; `prod.py` will fail fast).
- `DEBUG` — `True` locally, leave unset (defaults to `False`) in production.
- `ALLOWED_HOSTS` — comma-separated.
- `DATABASE_URL` — Postgres URL for prod; falls back to SQLite if unset.
- `EMAIL_BACKEND` — set to an SMTP backend in production; defaults to console (a `RuntimeWarning` is emitted in prod if left at console).
- `DEFAULT_FROM_EMAIL` — sender used by `quote_send`.
- `CSRF_TRUSTED_ORIGINS` — comma-separated, e.g. `https://your-app.up.railway.app`.
- `SECURE_SSL_REDIRECT` — defaults to `True` in prod; set `False` if behind a proxy that does not terminate TLS.
- `SECURE_HSTS_SECONDS` — defaults to 3600.

## Public quote flow

A draft quote gets a public token the first time it is **successfully** sent. The public URL is `/q/<token>/`. The first non-bot public GET transitions `Sent → Viewed`. Accept/Decline buttons write an `ActivityEvent` with IP and user-agent metadata. The owner can revoke the token from the quote detail page — the URL becomes unreachable afterward.

## Known academic limitations

- The public-view auto-transition relies on a user-agent heuristic; obscure preview/scanner bots may still trigger `Viewed`.
- Accept/decline on the public link is available to anyone holding the URL — there is no separate client authentication step.
- Audit metadata records the first `X-Forwarded-For` hop without validating a trusted proxy chain.
- Django admin can inspect records but quote `status` is read-only there so the state machine cannot be bypassed casually.
- Open signup with no email verification; duplicate usernames are blocked but email is optional.
- Tailwind is loaded via the Play CDN; for a production deployment we would replace it with a built bundle.
- Media uploads are served from local disk; on Railway with no persistent volume, logos do not survive restarts. A cloud storage backend would be required for a real deployment.
- Reorder is exposed as a server endpoint only — no drag-and-drop UI (see [docs/htmx-patterns.md](docs/htmx-patterns.md)).
- JSON responses share the same URLs as HTML; the `to_dict()` shape is not versioned (see ADR-0003).

## Commands

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py collectstatic --noinput
```

## Deployment

Railway uses `config.settings.prod` and reads the start command from `railway.toml` (not a Procfile). `DJANGO_SETTINGS_MODULE` is set inline so `migrate`, `collectstatic`, and `gunicorn` all run with production settings.

## Documentation

- [docs/schema.md](docs/schema.md) — data model overview and ER summary.
- [docs/htmx-patterns.md](docs/htmx-patterns.md) — HTMX patterns showcase.
- ADR-0001 — Decimal money.
- ADR-0002 — Server-side total recalculation.
- ADR-0003 — Same-URL content negotiation.
- ADR-0004 — Hand-rolled ReportLab PDF.
- ADR-0005 — USD-only currency (internationalization out of scope).

## License

MIT — see [LICENSE](LICENSE).
