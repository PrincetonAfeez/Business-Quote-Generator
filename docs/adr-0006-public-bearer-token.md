# ADR 0006: Public Bearer-Token Access

## Context

Clients receive quote links by email (`/q/<token>/`). The product must allow unauthenticated read, PDF download, and Accept/Decline without building a full client portal, password reset flow, or per-client user accounts. The grading scope treats the opaque URL as sufficient authorization for those actions.

## Decision

Each successfully sent quote receives a 32-character alphanumeric `public_token` (unique, revocable by setting it to `null`). Public views resolve quotes by token only — no session, no step-up auth. Accept/Decline POSTs require CSRF (same-origin form) but remain available to anyone who can load the page. Activity events record best-effort IP and user-agent metadata; `Sent → Viewed` skips requests matched by a substring bot heuristic.

Archived quotes return 404 on public URLs even if a token value remains in the database.

## Consequences

- Simple client experience: one link, no login.
- Anyone with the URL can accept or decline; leaked Referer headers or forwarded emails expand the trust circle.
- Bot filtering and IP capture are academic heuristics, not strong identity proof (see `docs/schema.md`).
- Revoking the token or archiving the quote invalidates the link; resend-after-revoke mints a new token.
- A production hardening pass would add rate limits, signed/expiring tokens, or client OTP — out of scope here.
