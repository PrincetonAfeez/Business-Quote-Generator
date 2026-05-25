# ADR 0004: Hand-Rolled ReportLab PDF

## Context

Owners and public recipients need a downloadable quote document. Third-party HTML-to-PDF stacks add heavy dependencies and make layout harder to audit for markup injection. The quote PDF layout is bounded: header, metadata table, line items, totals, terms, and a signature line.

## Decision

PDFs are generated on demand with ReportLab's platypus API. User-supplied text is HTML-escaped before being passed to `Paragraph`. PDFs are not stored; each download reflects the current quote state.

## Consequences

- Layout changes require Python edits rather than template tweaks, which is acceptable for a fixed academic scope.
- Public PDFs omit client email addresses while owner PDFs include them (`include_client_email` flag).
- ReportLab paragraph styles differ: `<br/>` works in `Normal` style but not in `Title` — multi-line business names are not supported without a style change (see comment in `pdf.py`).
