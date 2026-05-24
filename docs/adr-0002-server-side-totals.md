# ADR 2: Server-Side Total Recalculation

Totals are recalculated on the server after every line-item mutation. The client can preview values, but the server is the trust boundary and the single source of truth. This keeps PDF export, public views, JSON responses, and template rendering consistent.
