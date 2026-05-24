# ADR 3: Same URL Content Negotiation

The HTML and JSON surfaces share URLs. `Accept: application/json` returns JSON, while browser requests return HTML and HTMX requests return partial HTML.

This keeps ownership checks, query filters, and serialization concerns in one view path instead of splitting the future integration surface into a separate `/api/` namespace too early.
