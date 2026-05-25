# HTMX Patterns

## Single View, Two Responses

`quotes.views.quote_list`, `client_list`, `catalog_list`, and `dashboard` inspect `HX-Request`. Direct navigation returns full pages; HTMX requests return partials.

## `innerHTML`

The search fields on quote, client, and catalog lists target the feed/table containers and replace their inner content. Search and filter forms use `hx-push-url="true"` so filtered views are bookmarkable and the back button restores the previous query string.

## `outerHTML`

Quote rows, client rows, catalog rows, and line-item rows are replaced after inline edits or delete operations.

## `beforeend`

New quote line items append to `#line-items` with `hx-swap="beforeend"`. The dashboard feed uses a revealed sentinel to append additional activity rows.

## `none`

The line-item reorder endpoint returns an empty body with an `HX-Trigger` toast. It is the fire-and-forget pattern for an action whose only visible feedback is the toast notification.

## Public quote `Sent → Viewed`

The public quote page transitions `Sent → Viewed` on the first non-bot **full page GET** to `/q/<token>/`. This is not an HTMX request — it runs in the `elif` branch of `public_quote()` when the visitor loads the quote normally. Preview bots are filtered by user-agent heuristics in `is_probable_bot()`.

## `hx-swap-oob`

Line-item responses include the changed row plus out-of-band swaps for `#grand-total-panel` and `#favorite-count`. Quote list searches update pagination and quote count out of band.

## `hx-include`

The quote search input includes `#quote-filters`, so text search respects active status, client, date, and favorite filters.

## `HX-Trigger`

Mutating views call `add_toast()`, which sets `HX-Trigger: show-toast` with a JSON payload. `static/js/toasts.js` renders the notification.

## Infinite Scroll

`dashboard` paginates `ActivityEvent` records. The partial includes a final sentinel element with `hx-trigger="revealed"` to fetch the next page.
