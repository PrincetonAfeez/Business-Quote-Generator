# Template Partials

- `quotes/partials/_quote_card.html`: compact quote summary for dashboard lists.
- `quotes/partials/_quote_feed.html`: quote table rows plus HTMX out-of-band count and pagination updates.
- `quotes/partials/_filter_sidebar.html`: reusable quote filters and favorite count.
- `quotes/partials/_line_item_row.html`: editable quote line item row.
- `quotes/partials/_grand_total_panel.html`: totals panel reused on private and public quote pages.
- `quotes/partials/_toast.html`: server-side toast placeholder; client toasts are built by JavaScript.
- `quotes/partials/_activity_event.html`: single dashboard activity item.

Partials are named by the fragment they render and kept under `quotes/partials/` so full pages and HTMX views share the same markup.
