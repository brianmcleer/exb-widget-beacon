# Privacy and security

This page is written so you can hand it to a security or privacy reviewer as is.

## What is collected

One row per event with these fields: app id and title, widget name and version, an action name, an optional short detail string, error text for errors, the hostname the app was served from, the browser family, a random per page session id, the module version, and a timestamp. See the table in the README.

## What is never collected

- Usernames, account ids, display names, email addresses, IP addresses (the server sees the request IP as with any web request, but it is not stored in the table).
- Map extents, coordinates, addresses, parcel numbers, feature attributes, search terms, layer names, or anything a user typed.
- Query strings or tokens. The module strips `?...` from any URL in an error message and replaces `token=...` with `token=REDACTED` before sending. Email addresses in error text become `EMAIL`.
- Anything from the Experience Builder editor. Design mode is not counted.

The `session_id` is a random 16 character string generated when the page loads. It is not stored in cookies or local storage and cannot be linked to a person or to a later visit. It exists only so a dashboard can count sessions and group the events of one page view.

## Who can read the data

Two items are created:

| Item | Shared with | Capabilities | Purpose |
|---|---|---|---|
| `exb_widget_beacon` (hosted feature service) | Everyone | Create only | Widgets post rows here anonymously |
| `exb_widget_beacon_view` (hosted feature layer view) | Your organization | Query only | Dashboards and analysis |

The public item accepts `applyEdits` adds and nothing else: no query, no update, no delete, no attachments, no sync. `beacon_sink_setup.py verify` confirms an anonymous query is refused. Anyone on the internet could add a row to it, exactly as anyone could load your public web app; that is the same trust level as every public feature service with editing enabled, and the table holds nothing sensitive to read back because reading is not allowed.

The view is what people and dashboards use. It cannot be edited, and its sharing level is your organization, so the collected data never leaves your portal.

## Where the data goes

To your own portal, and nowhere else. The module has no built in URL. It discovers the table by searching the portal the app itself was loaded from for an item with the type keyword `exb-beacon-sink`. If you redistribute a widget that contains `beacon.ts`, other organizations that install it send nothing to you; unless they publish their own sink, they send nothing at all.

## Off switches

Any one of these turns telemetry off for the page: `telemetry: false` in the widget config, the browser's Do Not Track setting, `window.__exbBeaconDisabled = true`, no sink item on the portal, or the app being open in the editor. Widget authors can also expose a checkbox in their settings panel (see INTEGRATION.md).

## Failure behavior

Telemetry is best effort and can never affect the widget. Every code path is wrapped; posting is fire and forget with `keepalive`; the queue is dropped if the portal lookup fails. A broken or slow sink table slows nothing in the app.

## Retention

Nothing is deleted automatically. Storage is small (under 1 KB per row). If your policy requires a retention window, schedule a delete on the table, for example `occurred_at < CURRENT_TIMESTAMP - INTERVAL '365' DAY`, with a publisher account.
