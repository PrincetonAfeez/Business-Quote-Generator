# ADR 0005: USD Only — Currency Out of Scope

## Context

ADR-0001 standardizes decimal arithmetic, but it does not address which currency symbol to show or how to convert between currencies. The grading spec targets small US service businesses; adding multi-currency support would require per-profile currency codes, locale-aware formatting, and PDF template changes.

## Decision

All amounts are treated as US dollars. Templates use the `currency` filter and PDF totals hard-code a `$` prefix. No currency field exists on `CompanyProfile` or `Quote`.

## Consequences

- Formatting is consistent and simple across HTML, JSON, and PDF surfaces.
- Internationalization would require a new ADR covering stored currency codes, exchange rates, and locale-aware display.
- Hard-coded `$` in `pdf.py` is intentional, not an oversight.
