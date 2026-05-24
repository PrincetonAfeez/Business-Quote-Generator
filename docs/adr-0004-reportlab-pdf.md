# ADR 4: Hand-Rolled ReportLab PDF

PDFs are generated with ReportLab directly. The quote layout is bounded and predictable, so a small hand-written renderer is easier to audit than a broader quote-to-PDF package.

The PDF is generated on demand and not stored, avoiding stale documents after quote edits.
