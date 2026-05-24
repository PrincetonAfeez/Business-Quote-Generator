# HTMX Patterns

## Single View, Two Responses

`quotes.views.quote_list`, `client_list`, `catalog_list`, and `dashboard` inspect `HX-Request`. Direct navigation returns full pages; HTMX requests return partials.

## `innerHTML`

The search fields on quote, client, and catalog lists target the feed/table containers and replace their inner content.

## `outerHTML`

Quote rows, client rows, catalog rows, and line-item rows are replaced after inline edits or delete operations.

## `beforeend`

New quote line items append to `#line-items` with `hx-swap="beforeend"`. The dashboard feed uses a revealed sentinel to append additional activity rows.

## `none`

The reorder endpoint accepts posted positions and returns an empty response with an `HX-Trigger` toast. It is the fire-and-forget pattern for an action with no visual body.

## `hx-swap-oob`

Line-item responses include the changed row plus out-of-band swaps for `#grand-total-panel` and `#favorite-count`. Quote list searches update pagination and quote count out of band.

## `hx-include`

The quote search input includes `#quote-filters`, so text search respects active status, client, date, and favorite filters.

## `HX-Trigger`

Mutating views call `add_toast()`, which sets `HX-Trigger: show-toast` with a JSON payload. `static/js/toasts.js` renders the notification.

## Infinite Scroll

`dashboard` paginates `ActivityEvent` records. The partial includes a final sentinel element with `hx-trigger="revealed"` to fetch the next page.
