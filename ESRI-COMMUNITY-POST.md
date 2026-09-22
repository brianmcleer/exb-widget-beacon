# Widget Beacon: usage and error telemetry for Experience Builder custom widgets

*Esri Community, Experience Builder Custom Widgets board. Add two or three dashboard screenshots. No attachments; link the repository.*

If you build custom widgets, you have no idea which ones get used, which features inside them get pressed, which versions are still deployed, or what errors happen in the field. Widget Beacon fixes that.

**https://github.com/brianmcleer/exb-widget-beacon** (Apache 2.0)

## What you get

- Widgets ranked by use, per app. Esri's widgets are counted too, so you can compare yours with Legend or Print in the same app.
- Which features inside a widget get used. You decide what to count.
- Which widget versions are still out there, stacked by widget.
- Caught and uncaught errors with the first lines of the stack and the widget they came from.
- Browsers, activity per day, all filterable by period, widget and app.

## How it works

One TypeScript file goes in each widget. `beacon.init(props)` on mount, `b.action('export-pdf')` and `b.error(err, 'export-pdf')` where things happen. Events batch in the browser and post anonymously to a hosted table on your portal that accepts adds and nothing else. The widget finds the table by searching the app's own portal for an item tagged `exb-beacon-sink`. No item, nothing is sent. A query only view of the table, shared with your organization, feeds an ArcGIS Dashboards item the repo builds for you.

## What it does not collect

Usernames, IPs, locations, search terms, feature attributes, URLs with query strings. Tokens and email addresses are scrubbed from error text before it leaves the page. There is no URL in the code, so a widget with Beacon in it never reports to anyone but the portal it runs on. Do Not Track and a per widget `telemetry: false` switch are honored. The privacy page in the repo is written for your security reviewer.

## Setup

1. `setup/beacon_sink_setup.py create --write` against your portal (Enterprise 10.9.1+ with a hosting server, or ArcGIS Online). Creates the table, locks it to Create only, shares it with Everyone, tags it, creates the organization only view. `verify` should print ALL PASS.
2. Copy `src/beacon.ts` into each widget's `src/shared/`, add the init line and a few action lines, rebuild, republish the apps.
3. `setup/beacon_dashboard_setup.py --write` with your widget names. It prints the dashboard URL. Or skip Dashboards and drop `dashboard/index.html` on any web server: it reads the same view and adds sessions, an adoption matrix of widgets by app, hour of day patterns, errors grouped by message, and deployed versions checked against GitHub releases.

There is also a weekly email digest and an hourly alert script if you would rather not open a dashboard at all.

About fifteen minutes. The README has the exact commands, INTEGRATION.md covers naming and what not to send, FAQ.md covers ArcGIS Online credits, GDPR, why a public Create only service is fine, and what happens when the table is down (nothing; widgets never wait on telemetry).

## Compatibility

Tested on Experience Builder Developer Edition 1.21 and ArcGIS Enterprise 12.1. The module imports only `getAppStore` from `jimu-core`, no JSX, no dependencies, so 1.13 and later should work. The dashboard JSON matches what the Dashboards editor saves (schema 5.0.0); the repo explains how to refresh it if Esri changes that.

## Dashboard design

Built to Esri's *Author effective dashboards* guidance: one audience, one question per panel, the most important panel largest, muted palette with red reserved for errors, filters in the header. The layout is a Python function, so changing it is editing a list.

Issues and pull requests on GitHub.
