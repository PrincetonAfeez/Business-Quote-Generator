# Architecture Decision Record
## App — Business Quote Generator
**Business Workflow Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Business Workflow group requires a quote workflow application for small service businesses. The application must support authenticated business owners who manage a company profile, clients, catalog items, draft quotes, quote line items, quote totals, quote PDF output, email sending, public quote links, accept/decline tracking, and dashboard activity.

The project is not just a random quote generator. It is a transactional workflow app for creating business proposals and tracking their lifecycle. The core complexity is ownership, quote numbering, Decimal money calculations, quote status transitions, line-item editing, public token access, and export/send behavior.

The decision was to build the project as a Django 5 monolith using Django templates, HTMX partials, SQLite in development, PostgreSQL on Railway, WhiteNoise for production static assets, Pillow for uploaded logos, and ReportLab for PDF generation.

---

## Decisions

### Decision 1 — Django monolith over separate frontend/backend

**Chosen:** Django 5 with server-rendered templates, Django auth, ORM models, form classes, and HTMX-enhanced partial updates.

**Rejected:** SPA frontend, separate REST API, or static-only implementation.

**Reason:** The workflow is form-heavy and business-state-heavy. Django provides authentication, permissions, forms, email, ORM transactions, templates, and admin support in one stack. HTMX gives responsive line-item editing and quote-list updates without requiring a separate JavaScript application.

---

### Decision 2 — Per-user ownership through `OwnedManager`

**Chosen:** `CompanyProfile`, `Client`, `CatalogItem`, and `Quote` use an `OwnedManager` / `OwnedQuerySet.for_user(user)` pattern.

**Rejected:** Global quote/client/catalog tables or manually repeating ownership filters in every template.

**Reason:** Quotes, clients, catalog items, and company profile data are private business records. The manager pattern makes ownership queries explicit and reusable. View helpers such as `get_owned()` and `get_quote()` then apply permission checks around individual objects.

---

### Decision 3 — Quote numbers generated per user and year

**Chosen:** `QuoteCounter` stores one counter per owner/year and quote numbers use `Q-YYYY-0001` format.

**Rejected:** UUID-only quote identifiers or a single global sequence.

**Reason:** Business users expect readable quote numbers. Per-user, per-year counters make numbers understandable while avoiding cross-user leakage. `select_for_update()` protects the counter update during number generation.

---

### Decision 4 — Decimal money math with quantized cents

**Chosen:** Money values use `Decimal` and a helper quantizes values to two decimal places with `ROUND_HALF_UP`.

**Rejected:** Floating point arithmetic.

**Reason:** Quotes are financial documents. Decimal behavior is necessary for predictable line totals, discounts, taxes, and final totals. Tests cover rounding boundaries and discount/tax calculation behavior.

---

### Decision 5 — Guarded quote status transitions

**Chosen:** `Quote.TRANSITIONS` defines legal transitions: draft → sent/viewed/accepted/declined/expired paths, with final statuses locked.

**Rejected:** Allowing arbitrary status assignment.

**Reason:** Quote lifecycle matters. A quote should not jump from draft directly to accepted. Public view, accept, decline, sent, and expiry events need to update timestamps and activity records consistently.

---

### Decision 6 — Public quote links by random token

**Chosen:** A quote receives a 32-character public token the first time it is sent. Public URLs use `/q/<token>/`.

**Rejected:** Exposing quote primary keys publicly or requiring clients to create accounts.

**Reason:** Clients should be able to review and respond to a quote without authentication. A random token is simpler than client accounts and safer than exposing sequential database IDs.

---

### Decision 7 — Activity events for quote lifecycle traceability

**Chosen:** `ActivityEvent` records quote events such as created, sent, viewed, accepted, declined, duplicated, edited, and expired.

**Rejected:** Relying only on quote status fields.

**Reason:** Status says where the quote is now; events say how it got there. The dashboard uses activity events, and public accept/decline/view events store metadata such as IP and user agent.

---

### Decision 8 — ReportLab PDF generation over browser print or WeasyPrint

**Chosen:** Generate PDF files directly with ReportLab tables and paragraphs.

**Rejected:** Browser print-to-PDF, HTML-to-PDF dependencies, or external PDF service.

**Reason:** ReportLab is deterministic and does not require browser automation or native HTML rendering libraries. The resulting PDF includes company info, client info, line items, totals, terms, notes, and a signature line.

---

### Decision 9 — Email sending through Django email backend

**Chosen:** Use `send_mail()` and configurable `EMAIL_BACKEND` / `DEFAULT_FROM_EMAIL`.

**Rejected:** Hardcoding an SMTP provider or only showing public links without send action.

**Reason:** Django already provides an email abstraction. Local development can use console email while production can configure SMTP or provider-specific backends through environment.

---

### Decision 10 — Production deploy through Railway, Gunicorn, PostgreSQL, and WhiteNoise

**Chosen:** `railway.toml` runs migrate, collectstatic, and Gunicorn. Production settings parse `DATABASE_URL` and use WhiteNoise if installed.

**Rejected:** Manual server deployment or SQLite production.

**Reason:** Railway and Gunicorn are proportional to the app scope. PostgreSQL is appropriate for production quote data, and WhiteNoise avoids a separate static server.

---

## Consequences

**Positive:**
- The app demonstrates real workflow modeling, not just CRUD.
- Quote ownership is built into query patterns.
- Quote numbering is readable and scoped.
- Decimal totals avoid floating-point errors.
- Public quote links support client review without accounts.
- Activity events provide a traceable business timeline.
- PDFs are generated on demand without browser automation.
- HTMX supports focused line-item updates.
- Tests cover money math, status transitions, public flow, PDF smoke, JSON responses, and HTMX behavior.

**Negative / Trade-offs:**
- Public token URLs require careful secrecy because they act as bearer links.
- ReportLab PDFs are manually laid out and less flexible than HTML templates.
- Email sending depends on production email configuration.
- Media/logo storage uses local filesystem unless production storage is later added.
- There is no multi-staff organization model or role-based permission system.
- Production settings do not fail fast on all possible missing deployment variables beyond required `SECRET_KEY`.

---

## Alternatives Not Explored

- Multi-user company workspaces and roles.
- Full invoice/payment workflow.
- HTML-to-PDF rendering with theme parity.
- Stripe/payment acceptance.
- Quote versioning and approval workflow.
- External object storage for logos.
- Background email/PDF jobs.

---

*Constitution reference: Article 1 (architectural thinking), Article 3.4 (larger project classification), Article 4 (quality proportional to scope), Article 6 (verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — Business Quote Generator
**Business Workflow Group | Document 2 of 5**

---

## Overview

Business Quote Generator is a Django 5 app for creating, sending, tracking, and exporting service-business quotes. Authenticated users manage clients, catalog items, company defaults, and quotes. Public users can view a sent quote through a tokenized URL and accept or decline it.

**Project package:** `config`  
**Primary app:** `quotes`  
**Local settings:** `config.settings.dev`  
**Production settings:** `config.settings.prod`  
**Local database:** SQLite  
**Production database:** PostgreSQL through `DATABASE_URL`  
**PDF engine:** ReportLab  
**Interaction model:** Django templates + HTMX partials

---

## Data Flow

### Quote creation flow

```text
POST /quotes/new/
     │
     ▼
QuoteCreateForm(owner=request.user)
     │
     ├── validates selected Client belongs to owner
     ├── reads CompanyProfile defaults
     └── Quote.objects.create(...)
             ├── Quote.save()
             ├── _next_number()
             ├── QuoteCounter select_for_update()
             └── quote.record_event("created")
     │
     ▼
redirect /quotes/<pk>/
```

---

### Line-item editing flow

```text
POST /quotes/<pk>/lines/add/
     │
     ▼
get_quote(user, pk)
     │
     ▼
QuoteLineItemForm(owner=user)
     │
     ├── optional catalog item fills description/unit price
     └── item.save()
             ├── line_total = quantity * unit_price
             └── quote.calculate_totals(save=True)
     │
     ▼
record edited ActivityEvent
     │
     ▼
render HTMX line item response + OOB totals + toast
```

---

### Quote send/public flow

```text
POST /quotes/<pk>/send/
     │
     ▼
quote.ensure_public_token()
     │
     ▼
request.build_absolute_uri(quote.public_url)
     │
     ▼
send_mail(... public URL ...)
     │
     ▼
quote.transition_to(sent, event=sent, metadata={public_url})
```

```text
GET /q/<token>/
     │
     ▼
lookup quote by public_token
     │
     ├── check_expiry()
     ├── if status == sent: transition_to(viewed)
     └── render public quote
```

```text
POST /q/<token>/ action=accept|decline
     │
     ▼
transition_to(accepted|declined)
     │
     └── ActivityEvent metadata includes IP and user agent
```

---

### PDF flow

```text
GET /quotes/<pk>/pdf/
     │
     ▼
get_quote(user, pk)
     │
     ▼
profile_for(user)
     │
     ▼
render_quote_pdf(quote, profile)
     │
     ▼
ReportLab builds BytesIO PDF
     │
     ▼
HTTP attachment: <quote.number>.pdf
```

---

## Module-Level Structure

```text
Business-Quote-Generator/
  manage.py
  config/
    settings/
      base.py
      dev.py
      prod.py
    urls.py
    wsgi.py
    asgi.py
  quotes/
    admin.py
    apps.py
    forms.py
    models.py
    pdf.py
    urls.py
    views.py
    tests.py
    fixtures/
      seed.json
  templates/
    registration/
    quotes/
      partials/
  media/
  logs/
  requirements.txt
  railway.toml
```

---

## Module Dependency Graph

```text
config.urls
  ├── django admin
  ├── django auth views
  └── quotes.urls

quotes.urls
  └── quotes.views

quotes.views
  ├── forms
  ├── models
  ├── pdf.render_quote_pdf
  ├── django mail
  ├── HTMX helpers
  └── templates/partials

quotes.forms
  ├── Django forms
  ├── UserCreationForm
  └── owner-filtered querysets

quotes.models
  ├── Decimal money helpers
  ├── owned querysets/managers
  ├── quote numbering
  ├── status transitions
  ├── public token generation
  └── activity events

quotes.pdf
  └── ReportLab document/table/paragraph generation
```

---

## Core Data Structures

### `CompanyProfile`

One profile per user.

Fields:
- owner
- business name
- logo
- address
- tax ID
- default tax rate
- default terms
- default validity days

Used when creating quotes and rendering PDFs/emails.

---

### `Client`

User-owned customer record.

Fields:
- owner
- name
- company
- email
- phone
- billing address
- notes
- timestamps

Used as the required customer on a quote.

---

### `CatalogItem`

User-owned reusable service/product line.

Fields:
- owner
- name
- description
- default unit price
- unit
- timestamps

Supported units:
- hour
- day
- each
- sqft
- word
- page

---

### `QuoteCounter`

Per-owner, per-year counter.

Constraint:
```text
unique(owner, year)
```

Used to generate quote numbers such as:
```text
Q-2026-0001
```

---

### `Quote`

Main workflow object.

Important fields:
- owner
- number
- client
- status
- issue date
- expiry date
- tax rate
- discount type/value
- subtotal
- discount amount
- tax amount
- total
- notes
- terms
- public token
- viewed/accepted/declined timestamps
- favorite flag
- archived timestamp

Statuses:
- draft
- sent
- viewed
- accepted
- declined
- expired

Discount types:
- none
- percent
- flat

---

### `QuoteLineItem`

Quote child row.

Fields:
- quote
- optional catalog item
- description
- quantity
- unit price
- line total
- position

On save:
- line total is recalculated
- parent quote totals are recalculated

On delete:
- parent quote totals are recalculated

---

### `ActivityEvent`

Timeline row for quote history.

Event types:
- created
- sent
- viewed
- accepted
- declined
- duplicated
- edited
- expired

Fields:
- quote
- event type
- timestamp
- JSON metadata

---

## Function and Class Reference

### `money(value)`

Converts/quantizes a value to Decimal cents using `ROUND_HALF_UP`.

---

### `OwnedQuerySet.for_user(user)`

Returns records owned by an authenticated user, or an empty queryset for anonymous users.

---

### `Quote._next_number()`

Uses `QuoteCounter` and `select_for_update()` to generate the next per-user/year quote number.

---

### `Quote.ensure_public_token()`

Generates a unique 32-character public token if the quote does not already have one.

---

### `Quote.calculate_totals(save=False)`

Computes:
- subtotal from line item totals
- discount amount
- taxable subtotal
- tax amount
- final total

Validation:
- negative discounts are rejected
- percent discounts over 100 are rejected
- flat discounts are capped at subtotal

---

### `Quote.transition_to(new_status, event_type=None, metadata=None)`

Validates transition against `Quote.TRANSITIONS`, updates status/timestamps, saves, and records an activity event.

---

### `Quote.check_expiry()`

Marks a non-final quote expired when its expiry date is in the past.

---

### `Quote.duplicate_for_owner()`

Creates a new draft copy of a quote and its line items for the same owner, recalculates totals, and records a duplicated event.

---

### `QuoteLineItem.save()`

Recalculates `line_total` and parent quote totals.

---

### `QuoteLineItem.delete()`

Deletes the line item and recalculates parent quote totals.

---

### `QuoteCreateForm.save()`

Creates a quote using company profile defaults:
- default validity days
- default tax rate
- default terms

Then records a created event.

---

### `QuoteLineItemForm.clean()`

If a catalog item is selected, fills missing description and unit price from the catalog item. Requires either a description or catalog item.

---

### `render_quote_pdf(quote, profile=None)`

Builds a ReportLab PDF with:
- business name/address/tax ID
- quote metadata
- client block
- line item table
- totals table
- terms
- notes
- signature line

---

## Error Handling Strategy

- Authenticated owner routes use `get_owned()` or `get_quote()`.
- Cross-user quote/client/catalog/line-item access raises `PermissionDenied`.
- Missing objects return 404 through `get_object_or_404()`.
- Invalid quote transitions raise `InvalidTransition`.
- Invalid line-item or quote header forms return HTMX partials with status 422.
- Public quote invalid action returns HTTP 400.
- Public accept/decline ignores invalid final-state transitions rather than crashing.
- Expired quotes are lazily updated when accessed.
- Production settings require `SECRET_KEY` and optionally parse `DATABASE_URL` for PostgreSQL.

---

## External Dependencies

| Dependency | Purpose |
|---|---|
| Django | Web framework, ORM, auth, forms, email, templates |
| psycopg[binary] | PostgreSQL production database |
| python-dotenv | Local `.env` loading |
| Pillow | Uploaded logo support |
| ReportLab | PDF generation |
| WhiteNoise | Production static files |

---

## Concurrency Model

The app is synchronous Django.

Concurrency-sensitive area:
- quote number generation uses `transaction.atomic()` and `select_for_update()` on `QuoteCounter`.

There are:
- no async views
- no background jobs
- no task queue
- no websockets

---

## Known Limitations

- Public quote tokens are bearer links.
- No user roles or team workspaces.
- No invoice/payment conversion.
- No quote version history beyond activity events.
- PDF layout is manually maintained in Python.
- Email sending is synchronous.
- Logo/media persistence depends on filesystem unless external storage is added.
- No automated workflow file was found during this inspection.

---

## Design Patterns Used

- Django MVT
- Owned manager/queryset
- Owner-filtered forms
- Guarded state machine
- Activity event timeline
- Decimal money helper
- Transactional sequence counter
- HTMX partial response pattern
- Public token link
- ReportLab document builder

---

## Verification Summary

Tests cover:
- owner filtering
- Decimal totals and tax-after-discount behavior
- rounding boundaries
- negative discount rejection
- per-user/per-year quote numbering
- public token generation
- valid and invalid status transitions
- lazy expiry
- auth-required quote list
- cross-user permission denial
- JSON response negotiation
- HTMX quote list partial behavior
- HTMX mutation trigger headers
- public quote viewed transition
- public accept metadata
- PDF smoke output
- line-item HTMX response with out-of-band totals

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — Business Quote Generator
**Business Workflow Group | Document 3 of 5**

---

## Public Web Interface

| Method | Path | View | Success Status | Description |
|---|---|---|---:|---|
| `GET` | `/` | `dashboard` | 200 | Authenticated dashboard |
| `GET`/`POST` | `/signup/` | `signup` | 200/302 | Register account |
| `GET`/`POST` | `/profile/` | `profile_settings` | 200/302 | Company profile |
| `GET` | `/quotes/` | `quote_list` | 200 | Quote list; JSON/HTMX capable |
| `GET`/`POST` | `/quotes/new/` | `quote_create` | 200/302 | Create draft quote from client |
| `GET` | `/quotes/<pk>/` | `quote_detail` | 200 | Quote detail; JSON capable |
| `POST` | `/quotes/<pk>/update/` | `quote_update` | 200/422 | Update quote header |
| `POST` | `/quotes/<pk>/delete/` | `quote_delete` | 302 | Delete draft or archive non-draft |
| `POST` | `/quotes/<pk>/duplicate/` | `quote_duplicate` | 302 | Duplicate quote |
| `POST` | `/quotes/<pk>/send/` | `quote_send` | 302 | Generate public token, send email, mark sent |
| `POST` | `/quotes/<pk>/favorite/` | `quote_toggle_favorite` | 200 | Toggle favorite |
| `GET` | `/quotes/<pk>/pdf/` | `quote_pdf` | 200 | Owner PDF download |
| `POST` | `/quotes/<pk>/lines/add/` | `line_item_add` | 200/422 | Add line item |
| `POST` | `/quotes/<pk>/lines/reorder/` | `line_item_reorder` | 200/400 | Reorder line items |
| `POST` | `/quotes/<pk>/lines/<item_pk>/update/` | `line_item_update` | 200/422 | Update line item |
| `POST` | `/quotes/<pk>/lines/<item_pk>/delete/` | `line_item_delete` | 200 | Delete line item |
| `GET` | `/clients/` | `client_list` | 200 | Client list |
| `GET`/`POST` | `/clients/new/` | `client_create` | 200/302 | Create client |
| `GET`/`POST` | `/clients/<pk>/edit/` | `client_update` | 200/302 | Update client |
| `POST` | `/clients/<pk>/delete/` | `client_delete` | 200/302 | Delete client |
| `GET` | `/catalog/` | `catalog_list` | 200 | Catalog item list |
| `GET`/`POST` | `/catalog/new/` | `catalog_create` | 200/302 | Create catalog item |
| `GET`/`POST` | `/catalog/<pk>/edit/` | `catalog_update` | 200/302 | Update catalog item |
| `POST` | `/catalog/<pk>/delete/` | `catalog_delete` | 200/302 | Delete catalog item |
| `POST` | `/catalog/<pk>/add-to-quote/` | `catalog_add_to_quote` | 302 | Add catalog item to draft quote |
| `GET`/`POST` | `/q/<token>/` | `public_quote` | 200/400 | Public quote review/accept/decline |
| `GET` | `/q/<token>/pdf/` | `public_quote_pdf` | 200 | Public quote PDF |
| any | `/accounts/login/` | Django auth | varies | Login |
| any | `/accounts/logout/` | Django auth | varies | Logout |
| any | `/accounts/password_reset/` | Django auth | varies | Password reset |
| any | `/admin/` | Django admin | varies | Admin |

---

## Invocation Syntax

### Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata quotes/fixtures/seed.json
python manage.py runserver
```

Seed account:
```text
demo / demo12345
```

---

### Commands

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py collectstatic --noinput
```

---

### Production start command

```bash
python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application
```

---

## HTTP Input Contract

### Quote list filters

```text
GET /quotes/?q=<search>&status=<status>&client=<id>&start=<date>&end=<date>&favorites=1&sort=<field>&dir=<asc|desc>
```

Supported sort fields:
- number
- client
- issue_date
- total
- status

Response modes:
- normal HTML
- HTMX partial when `HX-Request: true`
- JSON when `Accept: application/json` and not HTMX

---

### Quote header form

Fields:
- client
- issue date
- expiry date
- tax rate
- discount type
- discount value
- notes
- terms
- favorite flag

Validation:
- client queryset is owner-filtered
- percent discount cannot exceed 100
- discount cannot be negative

---

### Line item form

Fields:
- catalog item
- description
- quantity
- unit price
- position

Rules:
- catalog item is optional
- description can be filled from catalog item
- unit price can be filled from catalog item
- description or catalog item is required

---

### Public quote action

```text
POST /q/<token>/
action=accept|decline
```

Invalid action:
```text
HTTP 400
```

---

## Output Contract

### Quote JSON

`GET /quotes/<pk>/` with `Accept: application/json` returns:

```json
{
  "id": 1,
  "number": "Q-2026-0001",
  "client": {...},
  "status": "draft",
  "issue_date": "2026-01-01",
  "expiry_date": "2026-01-31",
  "tax_rate": "8.25",
  "discount_type": "none",
  "discount_value": "0.00",
  "subtotal": "0.00",
  "discount_amount": "0.00",
  "tax_amount": "0.00",
  "total": "0.00",
  "line_items": []
}
```

---

### PDF response

Content type:
```text
application/pdf
```

Header:
```text
Content-Disposition: attachment; filename="<quote-number>.pdf"
```

File bytes begin with:
```text
%PDF
```

---

### HTMX mutation response

HTMX mutation responses may include:
- rendered partial HTML
- `HX-Trigger` containing `show-toast`
- out-of-band totals or quote row fragments
- status 422 for invalid forms

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | production | Django secret key |
| `DEBUG` | no | Debug flag |
| `ALLOWED_HOSTS` | production | Comma-separated hostnames |
| `DATABASE_URL` | production | PostgreSQL URL |
| `EMAIL_BACKEND` | no | Django email backend |
| `DEFAULT_FROM_EMAIL` | no | Sender address |
| `CSRF_TRUSTED_ORIGINS` | production with HTTPS | Trusted CSRF origins |
| `LOG_LEVEL` | no | Logging level |
| `DJANGO_SETTINGS_MODULE` | operationally | `config.settings.dev` or `config.settings.prod` |

---

## Configuration Files

### `.env`

Local environment file loaded through `python-dotenv`.

---

### `requirements.txt`

Dependencies:
- Django
- psycopg[binary]
- python-dotenv
- Pillow
- ReportLab
- WhiteNoise

---

### `railway.toml`

Deploy start command:
```text
python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application
```

---

## Side Effects

| Operation | Side Effect |
|---|---|
| Create quote | Creates quote number and created event |
| Add/update/delete line item | Recalculates quote totals and records edited event |
| Send quote | Creates token, sends email, records sent event |
| Public view | May transition sent quote to viewed |
| Public accept/decline | Updates status/timestamps and records metadata |
| Duplicate quote | Creates new quote and line items |
| Delete draft | Hard deletes draft |
| Delete non-draft | Archives quote with `archived_at` |
| PDF export | Generates PDF bytes on demand |
| collectstatic | Writes staticfiles for WhiteNoise |
| migrate | Updates database schema |

---

## Usage Examples

### Create a quote

1. Login.
2. Create a client.
3. Open `/quotes/new/`.
4. Select client.
5. Add line items.
6. Save/send/export PDF.

---

### Send a quote

```text
POST /quotes/<pk>/send/
```

Expected:
- public token exists
- email sent through configured backend
- status becomes sent
- activity event recorded

---

### Public acceptance

```text
POST /q/<token>/
action=accept
```

Expected:
- quote status becomes accepted
- accepted timestamp set
- activity event stores request metadata

---

### Owner PDF

```text
GET /quotes/<pk>/pdf/
```

---

### Public PDF

```text
GET /q/<token>/pdf/
```

---

## Public Python Interfaces

Important internal interfaces:
- `money`
- `Quote.calculate_totals`
- `Quote.transition_to`
- `Quote.ensure_public_token`
- `Quote.check_expiry`
- `Quote.duplicate_for_owner`
- `QuoteLineItem.save`
- `QuoteCreateForm.save`
- `QuoteLineItemForm.clean`
- `render_quote_pdf`
- `get_quote`
- `get_owned`
- `quote_queryset_from_request`

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — Business Quote Generator
**Business Workflow Group | Document 4 of 5**

---

## Requirements

### Local

- Python 3.12
- pip
- virtual environment support
- SQLite
- Django dependencies from `requirements.txt`
- email console backend for local testing

### Production

- Railway or equivalent host
- PostgreSQL database
- `SECRET_KEY`
- allowed hosts
- configured CSRF trusted origins
- email backend/provider
- Gunicorn
- WhiteNoise

---

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py loaddata quotes/fixtures/seed.json
python manage.py runserver
```

Open:
```text
http://127.0.0.1:8000/
```

Seed login:
```text
demo / demo12345
```

---

## Configuration Steps

### Development

Default from `manage.py`:
```text
config.settings.dev
```

Development behavior:
- `DEBUG = True`
- SQLite database
- console email backend
- local media serving through `config.urls`

---

### Production

Set:

```text
DJANGO_SETTINGS_MODULE=config.settings.prod
SECRET_KEY=<strong-secret>
ALLOWED_HOSTS=<hostnames>
DATABASE_URL=<postgres-url>
CSRF_TRUSTED_ORIGINS=<https-origins>
EMAIL_BACKEND=<email-backend>
DEFAULT_FROM_EMAIL=<sender>
```

Run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

---

## Standard Operating Procedures

### Create initial business profile

1. Login.
2. Open `/profile/`.
3. Set business name, address, tax ID, tax rate, default terms, and validity days.
4. Save.

---

### Create client

1. Open `/clients/`.
2. Add client name, company, email, phone, billing address, notes.
3. Save.

---

### Create catalog item

1. Open `/catalog/`.
2. Add service/product name, description, unit price, and unit.
3. Save.

---

### Create quote

1. Open `/quotes/new/`.
2. Select an owner-filtered client.
3. Create quote.
4. Add line items manually or from catalog.
5. Review subtotal, discounts, tax, and total.

---

### Send quote

1. Ensure client has email.
2. Click/post send action.
3. Confirm public token exists.
4. Confirm quote status becomes sent.
5. Confirm activity event records sent metadata.

---

### Accept or decline public quote

1. Open `/q/<token>/`.
2. Public view marks sent quotes as viewed.
3. Client clicks accept or decline.
4. Status/timestamps update and metadata is recorded.

---

### Export PDF

Authenticated:
```text
/quotes/<pk>/pdf/
```

Public:
```text
/q/<token>/pdf/
```

Expected:
- PDF attachment
- filename is quote number

---

## Health Checks

### Login page

```text
GET /accounts/login/
```

Healthy:
- HTTP 200
- login form visible

---

### Dashboard

```text
GET /
```

Healthy:
- authenticated user sees dashboard
- anonymous user redirects to login

---

### Quote list

```text
GET /quotes/
```

Healthy:
- HTTP 200 when logged in
- filters render
- JSON response works with Accept header

---

### Quote detail

```text
GET /quotes/<pk>/
```

Healthy:
- owner receives 200
- other user receives 403

---

### Public quote

```text
GET /q/<token>/
```

Healthy:
- HTTP 200 for valid token
- sent quote transitions to viewed

---

### PDF

```text
GET /quotes/<pk>/pdf/
```

Healthy:
- content type application/pdf
- response begins with `%PDF`

---

## Expected Outputs

### Quote number

```text
Q-2026-0001
```

---

### Public link

```text
/q/<32-character-token>/
```

---

### PDF attachment

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="Q-2026-0001.pdf"
```

---

### Invalid transition

```text
Cannot transition quote Q-2026-0001 from draft to accepted.
```

---

## Known Failure Modes

### Send quote fails

**Possible causes:**
- email backend not configured
- client has no email
- invalid status transition

**Resolution:**
- configure email backend
- add client email
- ensure quote is in draft/sent/viewed-appropriate state

---

### Public quote does not accept/decline

**Possible causes:**
- quote is already final
- token invalid
- action not `accept` or `decline`

**Resolution:**
- use valid token
- only open quotes can transition
- submit a supported action

---

### Totals look wrong

**Possible causes:**
- line item quantity/unit price input issue
- discount over 100 percent
- negative discount
- stale quote object before refresh

**Resolution:**
- check line items
- validate discount settings
- refresh detail page

---

### Cross-user object returns 403

**Trigger:** Accessing another user's quote/client/catalog/line item.

**Resolution:** Use records owned by the authenticated user.

---

### Production static files fail

**Possible causes:**
- `collectstatic` not run
- WhiteNoise not installed/configured
- missing static manifest

**Resolution:**
```bash
python manage.py collectstatic --noinput
```

---

### Production database failure

**Possible causes:**
- missing or malformed `DATABASE_URL`
- PostgreSQL unavailable

**Resolution:**
- verify `DATABASE_URL`
- verify Railway database service
- rerun migrations

---

## Troubleshooting Decision Tree

```text
App will not start
  ├── Dependencies missing?
  │     └── pip install -r requirements.txt
  ├── SECRET_KEY missing in prod?
  │     └── set SECRET_KEY
  ├── DB issue?
  │     └── check DATABASE_URL and migrate
  └── Static issue?
        └── collectstatic and verify WhiteNoise

Quote workflow broken
  ├── Cannot create quote?
  │     └── create client first
  ├── Cannot add catalog item?
  │     └── verify owner-filtered catalog item
  ├── Cannot send?
  │     └── configure email and valid status
  └── Cannot accept?
        └── check token and final status

PDF broken
  ├── ReportLab missing?
  │     └── pip install -r requirements.txt
  ├── Quote missing line items?
  │     └── PDF still renders but table may be sparse
  └── Permission issue?
        └── use owner route or public token route
```

---

## Dependency Failure Handling

### Python dependencies

```powershell
python -m pip install -r requirements.txt
```

---

### PostgreSQL

Check:
- `DATABASE_URL`
- network/service health
- psycopg install
- migrations

---

### Email

Use console email locally:
```text
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Configure SMTP/provider backend for production.

---

## Recovery Procedures

### Recover local DB

```powershell
Remove-Item db.sqlite3
python manage.py migrate
python manage.py loaddata quotes/fixtures/seed.json
```

---

### Recover from bad quote totals

1. Inspect line items.
2. Save/update one line item or quote header.
3. Run `calculate_totals(save=True)` through shell if needed.

---

### Recover from accidentally deleted draft

Draft delete is hard delete. Recreate or duplicate from an existing quote if available.

---

### Recover from archived non-draft quote

Set `archived_at` to null through admin or shell if an archive view is later not available.

---

## Logging Reference

Base settings write logs to:
- console
- `logs/app.log`

Format:
```text
timestamp [level] logger: message
```

Log level:
```text
LOG_LEVEL environment variable, default INFO
```

---

## Maintenance Notes

- Keep money math in Decimal.
- Add tests before changing quote transitions.
- Avoid exposing primary-key quote URLs publicly.
- Keep public token length and uniqueness intact.
- Configure production email before using send in production.
- Review filesystem media/logo behavior before Railway production use.
- Add external object storage if logos become important.
- Keep PDF smoke tests after changing ReportLab layout.
- Keep owner filtering on all client/catalog/quote routes.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints/trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — Business Quote Generator
**Business Workflow Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because quote generation is a good bridge between simple CRUD and real business workflow software. A user has clients, catalog items, company defaults, quotes, line items, totals, lifecycle status, PDF output, email delivery, and public acceptance. Each part is understandable on its own, but together they require architectural discipline.

Django was a strong fit because the app depends on models, forms, authentication, email, templates, permissions, and database transactions. HTMX was enough for a responsive quote editing experience without adding a frontend framework.

The most important design decision was modeling quotes as workflow objects instead of plain documents. Guarded transitions, public tokens, activity events, expiry checks, and timestamps make the quote lifecycle explicit.

---

## What Was Intentionally Omitted

**Payments:** Accepting a quote does not collect payment.

**Invoices:** Accepted quotes do not convert into invoices.

**Team workspaces:** Each user owns their own records. There are no organization roles.

**Full CRM:** Clients are simple records, not a sales pipeline.

**Quote versioning:** Activity events exist, but full revision history does not.

**Background jobs:** Email and PDF generation are synchronous.

**Complex PDF theming:** ReportLab output is practical and direct, not a theme engine.

**External media storage:** Logos are local file uploads unless production storage is added later.

---

## Biggest Weakness

The biggest weakness is public quote access via bearer token. It is simple and useful, but anyone with the link can view and act on the quote. This is acceptable for a scoped learner project and many lightweight quote workflows, but a higher-security production system might add expiration, signed actions, client email verification, or password-protected quote portals.

The second weakness is synchronous email/PDF behavior. For low volume, that is fine. At higher volume, sending email and generating PDFs should move to background jobs or queued workers.

The third weakness is local media storage. Company logos may disappear on ephemeral platforms unless external storage is configured.

---

## Scaling Considerations

**If teams are added:**
- introduce organization/workspace model
- add roles and permissions
- migrate owner fields to organization ownership
- audit all owner-filtered querysets

**If quote volume increases:**
- queue email sending
- consider PDF caching
- add indexes for quote filters
- add quote archive/search views

**If quote security increases:**
- shorten token validity
- add signed accept/decline forms
- add client email verification
- log more request metadata

**If the business workflow expands:**
- convert accepted quotes to invoices
- add payment links
- add quote versioning
- add reminder emails
- add status-change notifications

---

## What the Next Refactor Would Be

1. **Add an archive view** — non-draft deletes set `archived_at`, so a UI for archived quotes should exist.

2. **Move email sending behind a service** — wrap `send_mail()` in a testable quote notification service.

3. **Add background job option** — prepare PDF/email work for async processing.

4. **Add public token expiry or revoke control** — give owners a way to revoke public quote access.

5. **Add quote version snapshots** — preserve what the client saw when sent.

6. **Add storage abstraction for logos** — make production media storage explicit.

---

## What This Project Taught

- **Money math needs explicit rules.** Decimal quantization and discount validation are core design choices, not implementation details.

- **Workflow state should be guarded.** Status transition maps prevent impossible business states.

- **Readable identifiers matter.** Per-user yearly quote numbers are more useful than raw primary keys.

- **Public links are product decisions.** A token URL is convenient but must be treated as access control.

- **Activity events explain the workflow.** Events turn a quote from a row into a timeline.

- **HTMX fits line-item editing.** Server-rendered partials keep totals and rows consistent without frontend state duplication.

- **PDF generation is part of the architecture.** Choosing ReportLab affects layout, dependencies, tests, and future customization.

- **Tests protect financial behavior.** The tests around totals, rounding, transitions, public acceptance, and PDF output are the most important parts of the suite.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for Business Quote Generator.*
