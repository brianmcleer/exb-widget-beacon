# Changelog

Newest first.

## 1.2.0 (2026-09-18)

- New `dashboard/`: a standalone HTML dashboard (ArcGIS Maps SDK for sign in and queries, Chart.js) for any static web server. Sessions, change against the previous period, adoption matrix, weekday by hour heatmap, grouped error signatures with sample stacks, deployed versions against the latest GitHub release, widget health table, live feed, cross filtering, dark mode, CSV and PNG export, shareable URL state.
- New `setup/beacon_digest.py`: weekly HTML email digest and hourly alerts on new error signatures or error rate spikes, plain SMTP, brand neutral, dry run mode.
- `beacon_dashboard_setup.py` 1.4.1: errors by widget, features by widget, least used ranking, four band layout, and panel titles (Dashboards reads them from `caption`, so every chart had been unlabeled).

## 1.1.1 (2026-09-18)

- `beacon.ts`: the session id falls back to `crypto.getRandomValues` and then to a clock value, instead of `Math.random`. CodeQL flags `Math.random` as insecure randomness; the id is only used to group one page load's events, but the alert is noise in every repository that ships the file.

## 1.1.0 (2026-09-18)

- First public release.
- `beacon.ts` 1.1.0: portal lookup by type keyword, batching, scrubbing, Do Not Track and config off switches, unhandled error attribution, out of the box Esri widget counting (`loaded` once per page, `open` on OPENED).
- `beacon_sink_setup.py` 2.0.0: hosted table plus query only view, Create only capabilities, anonymous verification, works on Enterprise and ArcGIS Online.
- `beacon_dashboard_setup.py` 1.3.0: dashboard with header selectors, activity trend, popularity, features used, errors, versions in the field, apps and browsers.
