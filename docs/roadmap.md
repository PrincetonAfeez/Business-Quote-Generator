# Roadmap to 9.5+ (Academic)

Tracking checklist for raising every evaluation dimension to **9.5+**. Update checkboxes as work lands.

## Phase 1 — Integrity & HTMX ✅

- [x] Block `public_quote` / `public_quote_pdf` when quote is archived
- [x] Block `quote_send` when quote is archived
- [x] Send ordering: transition to `Sent` before `send_mail` on initial send
- [x] Filter form includes search input (`hx-include="#quote-search"`)
- [x] Line-item add 422: retarget swap via `HX-Retarget` + `_line_item_add_form.html`
- [x] Remove dead `#favorite-count` on quote detail; drop unused `favorite_count` in line-item views
- [x] Regression tests for the above (89 tests total)

## Phase 2 — UI parity ✅

- [x] Render terms & notes on `quote_detail.html` and `public_quote.html`
- [x] Read-only header: tax rate, discount summary, total preview
- [x] Public decline: distinct styling from accept
- [x] Public line items: column headers
- [x] Client/catalog tables: `<thead>`
- [x] Show company logo when uploaded (detail header + public quote)
- [x] Quote list: `hx-indicator` on search/filters

## Phase 3 — Client & catalog HTMX ✅

- [x] Inline create forms on list pages (`_client_create_form.html`, `_catalog_create_form.html`)
- [x] Inline edit via HX GET/POST on row (`_client_edit_row.html`, `_catalog_edit_row.html`)
- [x] Cancel returns read-only row (`client_row`, `catalog_row` endpoints)
- [x] Create/update validation retargets form wrapper on 422

## Phase 4 — Validation hardening ✅

- [x] Flat discount vs subtotal validated on first save (via `_validate_discount_fields`)
- [x] Reject `discount_type=none` with positive `discount_value`
- [x] `QuoteLineItem.clean()`: quote existence + catalog/quote owner alignment
- [x] Unify `ValueError` → `ValidationError` in `calculate_totals()` for corrupt discounts
- [x] Client email normalized to lowercase on save

## Phase 5 — Tests & docs ✅

- [x] 108 tests; README count updated
- [x] Fixed `htmx-patterns.md` / `_README.md` drift (toasts path, OOB scope, removed dead `_toast.html`)
- [x] ADR-0006: public bearer-token trust model

## Phase 6 — Accessibility ✅

- [x] `aria-label` on icon buttons; `aria-hidden` on decorative icons
- [x] Label `for`/`id` on line-item fields
- [x] Skip link, focus-visible, messages `role="alert"`
- [x] Resolve duplicate `#favorite-count` IDs (`sidebar-favorite-count`)

## Phase 7 — Polish ✅

- [x] HTMX pagination on quote list
- [x] Generic send error messages (no SMTP strings)
- [x] CI: `check --deploy` against prod settings
- [x] Pin `requirements.txt` versions
