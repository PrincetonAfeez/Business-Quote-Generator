# ADR 0002: Server-Side Total Recalculation

## Context

Quotes expose totals in HTML partials, JSON responses, public pages, and PDF downloads. If the browser computed totals independently, any mismatch between client preview and server truth would surface as billing disputes or inconsistent exports after a line-item edit.

## Decision

`Quote.calculate_totals()` recomputes subtotal, discount, tax, and total on the server after every line-item mutation. `QuoteLineItem.save()` and `.delete()` call it automatically; stored columns on `Quote` are the single source of truth for all surfaces.

## Consequences

- HTMX responses can include out-of-band total panels without trusting posted form values.
- Bulk updates via `QuerySet.update()` bypass model hooks — contributors must not use it for fields that affect `line_total` (see the comment on `QuoteLineItem`).
- Slightly more database work per edit, which is acceptable at the expected quote volume for a small-business tool.
