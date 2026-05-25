# Template Partials

- `quotes/partials/_quote_row.html`: single quote row used in the quote list table.
- `quotes/partials/_quote_card.html`: compact quote summary used on the dashboard upcoming-expiries panel.
- `quotes/partials/_quote_feed_rows.html`: `<tr>` rows for the quote list tbody.
- `quotes/partials/_quote_feed_oob.html`: out-of-band count, pagination, and favorite-count updates for HTMX list refreshes.
- `quotes/partials/_quote_feed.html`: HTMX response combining feed rows and OOB fragments.
- `quotes/partials/_quote_row_response.html`: HX response after favoriting a quote; replaces the row and updates the sidebar count OOB.
- `quotes/partials/_quote_header.html` / `_quote_header_form.html`: detail-page header card and inline edit form (`innerHTML` swap into `#quote-header`).
- `quotes/partials/_quote_terms_notes.html`: read-only notes and terms block (detail + public pages).
- `quotes/partials/_line_item_row.html`: editable or read-only quote line item row depending on `quote_is_editable`.
- `quotes/partials/_line_item_form.html`: shared widget block for the line item form (used both for add and inline edit).
- `quotes/partials/_line_item_add_form.html`: wrapper for the add-line-item HTMX form (`HX-Retarget` on validation errors).
- `quotes/partials/_line_item_response.html` / `_line_item_delete_response.html`: HX responses after a line-item mutation; OOB totals panel only.
- `quotes/partials/_grand_total_panel.html`: static totals panel on full-page renders.
- `quotes/partials/_grand_total_panel_oob.html`: same totals panel with `hx-swap-oob` for HTMX mutations.
- `quotes/partials/_filter_sidebar.html`: reusable quote filters and favorite count.
- `quotes/partials/_pagination.html`: paginator controls reused across list views.
- `quotes/partials/_favorite_count.html`: OOB span that holds the favorites count badge (quote list sidebar only).
- `quotes/partials/_client_table.html` / `_client_row.html` / `_client_create_form.html` / `_client_edit_row.html`: client list with inline HTMX create/edit.
- `quotes/partials/_catalog_table.html` / `_catalog_row.html` / `_catalog_create_form.html` / `_catalog_edit_row.html`: catalog list with inline HTMX create/edit.
- `quotes/partials/_activity_event.html` / `_activity_feed_items.html`: dashboard activity feed.
- `quotes/partials/_public_thank_you.html`: HTMX response after Accept/Decline (includes OOB status badge swap).
- `quotes/partials/_public_status_panel.html`: static panel for terminal public quote states (accepted, declined, expired).

Partials are named by the fragment they render and kept under `quotes/partials/` so full pages and HTMX views share the same markup. Auth templates (`login`, `signup`, password reset) live under project-level `templates/registration/` (see `config/settings/base.py` `DIRS`).
