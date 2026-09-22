# Changelog

Newest first.

## 1.1.1 (2026-09-18)

- `beacon.ts`: the session id falls back to `crypto.getRandomValues` and then to a clock value, instead of `Math.random`. CodeQL flags `Math.random` as insecure randomness; the id is only used to group one page load's events, but the alert is noise in every repository that ships the file.

## 1.1.0 (2026-09-18)

- First public release.
- `beacon.ts` 1.1.0: portal lookup by type keyword, batching, scrubbing, Do Not Track and config off switches, unhandled error attribution, out of the box Esri widget counting (`loaded` once per page, `open` on OPENED).
- `beacon_sink_setup.py` 2.0.0: hosted table plus query only view, Create only capabilities, anonymous verification, works on Enterprise and ArcGIS Online.
- `beacon_dashboard_setup.py` 1.3.0: dashboard with header selectors, activity trend, popularity, features used, errors, versions in the field, apps and browsers.
