# Data Model

This document is a human-readable summary of the schema in `quotes/models.py` for grading. It complements the Django migrations, which are the source of truth.

## Entities

### User (Django built-in)
Standard `django.contrib.auth.User`. Every domain object is owned by one user.

### CompanyProfile (1 ↔ 1 User)
The owning business's branding and defaults applied to new quotes.

| Field | Type | Notes |
|------|------|------|
| owner | OneToOne(User) | CASCADE delete |
| business_name | CharField(200) | required |
| logo | ImageField | optional, stored under `media/logos/` |
| address | TextField | optional |
| tax_id | CharField(80) | optional |
| default_tax_rate | Decimal(5,2) | validators: 0 ≤ x ≤ 100 |
| default_terms | TextField | optional |
| default_validity_days | PositiveInteger | default 30 |

### Client (N ↔ 1 User)
A customer/contact a quote can be issued to.

| Field | Type | Notes |
|------|------|------|
| owner | FK(User) | CASCADE |
| name | CharField(200) | required |
| company | CharField(200) | optional |
| email | EmailField | optional; **unique per owner when non-empty** |
| phone | CharField(50) | optional |
| billing_address | TextField | optional |
| notes | TextField | optional |
| created_at / updated_at | DateTime | auto |

Constraint: `UniqueConstraint(owner, email, condition=~Q(email=""))`.

### CatalogItem (N ↔ 1 User)
A reusable line item template.

| Field | Type | Notes |
|------|------|------|
| owner | FK(User) | CASCADE |
| name | CharField(200) | required |
| description | TextField | optional |
| default_unit_price | Decimal(12,2) | validators: ≥ 0 |
| unit | CharField(20) choices=hour/day/each/sqft/word/page | default `each` |
| created_at / updated_at | DateTime | auto |

### QuoteCounter (N ↔ 1 User)
Counter table for per-user, per-year quote numbering.

| Field | Type | Notes |
|------|------|------|
| owner | FK(User) | CASCADE |
| year | PositiveInteger | |
| last_number | PositiveInteger | default 0 |

Constraint: `UniqueConstraint(owner, year)`.

### Quote (N ↔ 1 User, N ↔ 1 Client)
The central aggregate.

| Field | Type | Notes |
|------|------|------|
| owner | FK(User) | CASCADE |
| number | CharField(20) | `Q-YYYY-####`, allocated atomically inside `save()` |
| client | FK(Client) | **PROTECT** — cannot delete a client with quotes |
| status | CharField(20) choices | draft/sent/viewed/accepted/declined/expired |
| issue_date | DateField | default today |
| expiry_date | DateField | required, must be > issue_date |
| tax_rate | Decimal(5,2) | 0 ≤ x ≤ 100 |
| discount_type | CharField(20) | none/percent/flat |
| discount_value | Decimal(12,2) | ≥ 0; ≤ 100 if percent; ≤ subtotal if flat (checked in `clean()`) |
| subtotal / tax_amount / discount_amount / total | Decimal(12,2) | server-computed |
| notes / terms | TextField | optional |
| public_token | CharField(32), unique | issued by `ensure_public_token`, revocable |
| viewed_at / accepted_at / declined_at | DateTime | audit |
| is_favorite | Boolean | for filter sidebar |
| archived_at | DateTime | soft-archive for non-Draft deletes |
| created_at / updated_at | DateTime | auto |

Constraint: `UniqueConstraint(owner, number)`.

### QuoteLineItem (N ↔ 1 Quote, optional ↔ 1 CatalogItem)

| Field | Type | Notes |
|------|------|------|
| quote | FK(Quote) | CASCADE |
| catalog_item | FK(CatalogItem) | SET_NULL when the catalog item is deleted |
| description | TextField | required |
| quantity | Decimal(12,2) | ≥ 0.01 |
| unit_price | Decimal(12,2) | ≥ 0 |
| line_total | Decimal(12,2) | recomputed in `save()` |
| position | PositiveInteger | for ordering |

### ActivityEvent (N ↔ 1 Quote)
Append-only audit log.

| Field | Type | Notes |
|------|------|------|
| quote | FK(Quote) | CASCADE |
| event_type | CharField(20) choices | created/sent/viewed/accepted/declined/duplicated/edited/expired |
| timestamp | DateTime | auto_now_add |
| metadata | JSONField | per-event payload (IP, UA, public_url, etc.) |

## Relationship summary

```
User 1 ── 1 CompanyProfile
User 1 ── * Client
User 1 ── * CatalogItem
User 1 ── * QuoteCounter (per year)
User 1 ── * Quote
Client 1 ── * Quote          (PROTECT)
Quote 1 ── * QuoteLineItem   (CASCADE)
Quote 1 ── * ActivityEvent   (CASCADE)
CatalogItem 1 ── * QuoteLineItem (SET_NULL)
```

## State machine

```
draft ──► sent ──► viewed ──► accepted
   │        │         │   └──► declined
   │        │         └──► expired
   │        └──► accepted / declined / expired
   └──► expired
```

All transitions are defined in `Quote.TRANSITIONS` and enforced by `Quote.transition_to()`. Once a quote leaves `draft`, edits are blocked at the view layer via `quote_is_editable()`.

## Money calculation

Implemented once in `Quote.calculate_totals()`:

```
subtotal       = Sum(line_item.line_total) (SQL aggregate)
discount       = min(money(discount_value or percent of subtotal), subtotal)
taxable        = subtotal - discount
tax            = money(taxable * tax_rate / 100)
total          = money(taxable + tax)
```

Every value is `Decimal`, quantized with `ROUND_HALF_UP` at every boundary. Tax is applied **after** discount.
