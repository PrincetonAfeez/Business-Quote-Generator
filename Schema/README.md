# Business Quote Generator — Schema Folder

This folder contains a simple academic schema package for the Business Quote Generator Django project.

## Files

- `company-profile.schema.json`
- `client.schema.json`
- `catalog-item.schema.json`
- `quote-counter.schema.json`
- `quote.schema.json`
- `quote-line-item.schema.json`
- `activity-event.schema.json`
- `database.schema.sql`
- `relationship-summary.md`
- `state-machine.md`

## Notes

These files are a readable schema summary for grading/documentation. The Django models and migrations remain the source of truth for the actual application database.

Core rules represented here:

- Every domain object is scoped to an authenticated owner/user.
- Quote numbers are unique per owner.
- Client email is normalized and unique per owner when non-empty.
- Quote expiry date must be after issue date.
- Tax rates are constrained to 0–100.
- Quote line item quantity must be at least 0.01.
- Quote line item unit price must be at least 0.00.
- Quote totals are calculated server-side from line items, discount, and tax.
