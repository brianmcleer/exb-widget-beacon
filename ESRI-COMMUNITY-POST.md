# Widget Beacon: find out which of your Experience Builder widgets people actually use

*Draft for Esri Community, Experience Builder Custom Widgets board. Attach two or three dashboard screenshots. Do not attach files; link the repository.*

If you build custom widgets for ArcGIS Experience Builder, you probably have the same blind spot I had. The widgets ship, the apps go live, and after that the only signal you get is an occasional email when something breaks. You do not know which widgets get used, which features inside them anyone presses, which old versions are still deployed in apps you forgot about, or what errors happen in the field.

Widget Beacon is a small, open source answer to that. It is one TypeScript file you drop into each widget, a hosted table on your own portal that collects anonymous events, and an ArcGIS Dashboards item that turns them into pictures. It is on GitHub under the Apache 2.0 license:

**https://github.com/brianmcleer/exb-widget-beacon**

## What it tells you

- Which widgets are used, how much, in which apps, ranked. Esri's own widgets are counted too, so you can see your custom widget next to Legend or Print in the same app.
- Which features inside a widget get used (you decide what to count: export PDF, search, draw, whatever matters).
- Which widget versions are still out there, stacked by widget, so you know what to update.
- Errors, caught and uncaught, with the first lines of the stack and the widget they came from, without waiting for someone to report them.
- Browsers, activity per day, and everything filterable by period, widget and app.

## How it works, in one paragraph

A widget calls `beacon.init(props)` when it mounts and `b.action('export-pdf')` or `b.error(err, 'export-pdf')` where things happen. Events queue in the browser and post in batches to a hosted table's `applyEdits` endpoint, anonymously. The table accepts adds and nothing else. The widget finds the table by asking the portal that served the app for an item tagged `exb-beacon-sink`; if there is none, telemetry is off and nothing is sent anywhere. A query only view of the table, shared with your organization, feeds the dashboard.

## What it does not do

It does not collect usernames, IP addresses, locations, search terms, feature attributes or URLs with query strings. Tokens and email addresses are scrubbed out of error text before it leaves the page. There is no URL in the code, so a widget with Beacon in it that you download from someone else sends nothing to that someone. Honoring Do Not Track and a per widget `telemetry: false` config switch are built in. The privacy page in the repository is written so you can hand it to your security reviewer.

## Setup, roughly fifteen minutes

1. Run `setup/beacon_sink_setup.py create --write` against your portal (Enterprise 10.9.1 or later with a hosting server, or ArcGIS Online). It creates the table, locks it to Create only, shares it with Everyone, tags it, and creates the organization only view. Run `verify` and you should see ALL PASS.
2. Copy `src/beacon.ts` into each widget's `src/shared/`, add the init line and a few action lines, rebuild, republish the apps.
3. Run `setup/beacon_dashboard_setup.py --write` with the list of your widget names. It builds the dashboard and prints the URL.

The README walks through each step with the exact commands, the INTEGRATION page covers naming and what not to send, and the FAQ covers the questions I expect (ArcGIS Online credits, GDPR, why a public editable service is fine here, what happens when the table is down: nothing, widgets never wait on telemetry).

## Compatibility

Tested on Experience Builder Developer Edition 1.21 and ArcGIS Enterprise 12.1. The module imports only `getAppStore` from `jimu-core` and has no JSX and no dependencies, so it should be fine from 1.13 onward. The dashboard JSON was copied from what the Dashboards editor saves (schema 5.0.0); if Esri changes that, the repository explains how to refresh it in five minutes.

## A note on the dashboard design

I went through Esri's *Author effective dashboards* documentation and the *Designing effective dashboards* blog before laying it out: one audience (the people who maintain the widgets), one question per panel, the most important panel largest, a muted palette with red reserved for errors, numbers shown with context, and filters in the header rather than separate dashboards. The whole layout is a Python function, so changing it is editing a list, not clicking through the editor.

Questions and pull requests are welcome on GitHub. If you deploy it, I would be glad to hear what the numbers taught you about your own widgets; mine were humbling.
