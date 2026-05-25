# ADR 0001: Decimal For Money

## Context

Quote line items, discounts, tax, and totals must round predictably for PDF export, public views, and owner dashboards. Binary floating point cannot represent many decimal fractions exactly — for example, `0.1 + 0.2` in IEEE-754 produces a value slightly above `0.3`. For invoicing software, even sub-cent drift is unacceptable and erodes trust in exported documents.

## Decision

All monetary fields use `DecimalField` in the database and `decimal.Decimal` in Python. Display and persistence pass through a shared `money()` helper that quantizes to two decimal places with `ROUND_HALF_UP`.

## Consequences

- Totals remain stable across ORM aggregation, template filters, JSON serialization, and PDF rendering.
- Developers must avoid mixing floats into money math; tests assert boundary rounding explicitly.
- Currency symbols and locale formatting are out of scope (see ADR-0005); amounts are stored and displayed as plain decimal numbers with a hard-coded `$` prefix in templates and PDFs.
