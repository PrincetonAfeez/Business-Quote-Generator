# ADR 0003: Same-URL Content Negotiation 0003

## Context

The grading spec calls for both a browser UI and a machine-readable surface. A separate `/api/` namespace would duplicate ownership checks, filtering, pagination, and serialization logic across parallel view modules.

## Decision

Shared list and detail views inspect the `Accept` header and `HX-Request`. Browser navigation returns full HTML templates, HTMX requests return partials, and `Accept: application/json` returns JSON payloads built from the same queryset helpers.

## Consequences

- One code path enforces owner scoping and query filters for HTML and JSON consumers.
- Clients must send explicit `Accept` headers for JSON; accidental JSON responses to browsers are avoided by checking HTMX first.
- Future API versioning can still introduce a dedicated namespace if external integrators need stable contracts beyond the current `to_dict()` shape.
