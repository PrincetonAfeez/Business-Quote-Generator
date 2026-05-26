# Relationship Summary

```text
User 1 ── 1 CompanyProfile
User 1 ── * Client
User 1 ── * CatalogItem
User 1 ── * QuoteCounter
User 1 ── * Quote

Client 1 ── * Quote          (PROTECT / restrict delete)
Quote 1 ── * QuoteLineItem   (CASCADE)
Quote 1 ── * ActivityEvent   (CASCADE)
CatalogItem 1 ── * QuoteLineItem (SET NULL)
```

## Ownership Rules

- `Client.owner_id`, `CatalogItem.owner_id`, `CompanyProfile.owner_id`, `Quote.owner_id`, and `QuoteCounter.owner_id` point to the Django user.
- A `Quote.client_id` must point to a client owned by the same user.
- A line item's optional `catalog_item_id` must point to a catalog item owned by the quote owner.
