# HTMX Patterns 

Static assets: toast JavaScript lives at `quotes/static/js/toasts.js` (served as `{% static 'js/toasts.js' %}`).

## Single View, Two Responses

`quotes.views.quote_list`, `client_list`, `catalog_list`, and `dashboard` inspect `HX-Request`. Direct navigation returns full pages; HTMX requests return partials.

## `innerHTML`

The search fields on quote, client, and catalog lists target the feed/table containers and replace their inner content. Search and filter forms use `hx-push-url="true"` so filtered views are bookmarkable and the back button restores the previous query string.

Quote header edits swap into `#quote-header` via `innerHTML`.

## `outerHTML`

Quote rows, client rows, catalog rows, and line-item rows are replaced after inline edits or delete operations.

## `beforeend`

New quote line items append to `#line-items` with `hx-swap="beforeend"`. Client and catalog creates append a new `<tr>` to `#client-rows` / `#catalog-rows`. The dashboard feed uses a revealed sentinel to append additional activity rows.

## Client & catalog inline CRUD

List pages embed create forms (`#client-create`, `#catalog-create`) that POST via HTMX. Edit buttons issue an HX GET to the update URL, swapping the row for an inline edit form. Cancel fetches the read-only row partial from `/clients/<pk>/row/` or `/catalog/<pk>/row/`. Validation errors on create use `HX-Retarget` to replace the form wrapper.

## `HX-Retarget` / `HX-Reswap`

Line-item add failures and client/catalog create validation errors return `422` with `HX-Retarget` pointing at the form wrapper (`#line-item-add`, `#client-create`, `#catalog-create`) so HTMX swaps errors into the page instead of silently ignoring 4xx responses.

## `none`

The line-item reorder endpoint returns an empty body with an `HX-Trigger` toast. It is the fire-and-forget pattern for an action whose only visible feedback is the toast notification. **There is no drag-and-drop UI** — reorder is server/API-only for this academic scope.

## Public quote `Sent → Viewed`

The public quote page transitions `Sent → Viewed` on the first non-bot **full page GET** to `/q/<token>/`. This is not an HTMX request — it runs in the `elif` branch of `public_quote()` when the visitor loads the quote normally. Preview bots are filtered by user-agent heuristics in `is_probable_bot()`. See ADR-0006 for the bearer-token trust model.

## `hx-swap-oob`

Line-item responses include the changed row plus an out-of-band swap for `#grand-total-panel` only. Favorite count OOB updates happen on quote-list search/filter refresh and favorite-toggle responses (`_quote_feed_oob.html`, `_quote_row_response.html`). Quote list searches update pagination and quote count out of band. Pagination links (`_pagination.html`) use the same HTMX target/select/include pattern as search so page changes refresh rows without a full reload.

## `hx-include`

The quote search input includes `#quote-filters`, and the filter sidebar includes `#quote-search`, so text search and filter changes stay in sync on HTMX refreshes.

## `HX-Trigger`

Mutating views call `add_toast()`, which sets `HX-Trigger: show-toast` with a JSON payload. `quotes/static/js/toasts.js` renders the notification client-side.

## Infinite Scroll

`dashboard` paginates `ActivityEvent` records. The partial includes a final sentinel element with `hx-trigger="revealed"` to fetch the next page.

## Loading indicators

Quote, client, and catalog list searches set `hx-indicator` to a visible “Updating…” span; CSS in `quotes/static/css/app.css` toggles `.htmx-indicator` during requests.
