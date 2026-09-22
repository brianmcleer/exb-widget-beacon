# Widget Beacon for ArcGIS Experience Builder

Anonymous usage and error telemetry for custom Experience Builder widgets, with a hosted table to collect it and an ArcGIS Dashboards item to read it. One TypeScript file goes in each widget. Two Python scripts stand up the table and the dashboard on your own portal. Nothing leaves your organization.

It answers the questions widget authors usually cannot: which of my widgets are actually used, in which apps, which features inside them get pressed, which versions are still deployed, which browsers people use, and what errors happen in the field that nobody reports.

It also counts Esri's own widgets, so you can compare your custom widgets with the out of the box ones in the same apps.

## How it works

```
Browser (any app that contains an instrumented widget)
   beacon.ts  --applyEdits (anonymous, Create only)-->  hosted table  exb_widget_beacon
                                                              |
                                                     query-only view  exb_widget_beacon_view  (your organization)
                                                              |
                                                     ArcGIS Dashboards item
```

1. A widget calls `beacon.init(props)` once when it mounts. That records an "open" event.
2. The widget calls `b.action('export-pdf')` for the handful of things worth counting, and `b.error(err, 'export-pdf')` in catch blocks.
3. Events queue in memory and are posted in batches (every 10 seconds, at 20 events, and when the page hides) to the table's `applyEdits` endpoint. No token is sent. The table accepts adds and nothing else.
4. The widget finds the table by asking the app's own portal for a public item carrying the type keyword `exb-beacon-sink`. That lookup happens once per page load and is cached for the session.
5. If the portal has no such item, telemetry is off. Nothing is sent anywhere.

Point 5 is the important one for anyone redistributing a widget: an organization that installs your widget sends nothing to you and nothing to anyone, unless it publishes its own sink table. The module has no built in URL.

## What gets recorded

One row per event. No usernames, no coordinates, no attribute values, no addresses, no URLs with query strings.

| Field | Example | Notes |
|---|---|---|
| `app_id` | `12` | Experience Builder app id |
| `app_name` | `City Map` | App title |
| `widget_name` | `print-advanced` | Manifest name; for Esri widgets, Esri's name (`legend`, `print`) |
| `widget_version` | `1.6.5` | Manifest version; for Esri widgets, the Experience Builder version |
| `action` | `open`, `export-pdf`, `error`, `loaded`, `unhandled-error` | Short stable names |
| `detail` | `letter landscape` | Optional, 250 characters, scrubbed |
| `error_text` | `TypeError: ... \| stack line \| ...` | First lines of the stack, 1000 characters, scrubbed |
| `host` | `maps.example.org` | Hostname the app was served from |
| `browser` | `Chrome`, `Edge`, `Firefox`, `Safari`, `Opera`, `Other` | Family only |
| `session_id` | `3f9a...` | Random per page load, never persisted |
| `beacon_version` | `1.1.0` | Version of beacon.ts |
| `occurred_at` | date | Browser clock |

Scrubbing: anything matching `token=` is replaced with `token=REDACTED`, query strings are cut off URLs, and email addresses become `EMAIL`. See [docs/PRIVACY.md](docs/PRIVACY.md).

## Off switches

Any one of these disables telemetry for that page:

- the app builder sets `"telemetry": false` in the widget's config (add a checkbox to your settings panel if you want to expose it);
- the browser sends Do Not Track;
- a page sets `window.__exbBeaconDisabled = true` before widgets load;
- the portal has no item tagged `exb-beacon-sink`;
- the app is open in the Experience Builder editor (design mode is never counted).

## Setup

You need a publisher account on ArcGIS Enterprise (10.9.1 or later with a hosting server) or ArcGIS Online, Python with the [ArcGIS API for Python](https://developers.arcgis.com/python/) (ArcGIS Pro's environment has it), and your widgets' source.

### 1. Create the table and the view

PowerShell or Command Prompt, regular. Dry run first:

```
python setup/beacon_sink_setup.py create --portal https://gis.example.org/portal --user publisher
```

Then for real:

```
python setup/beacon_sink_setup.py create --portal https://gis.example.org/portal --user publisher --write
python setup/beacon_sink_setup.py verify --portal https://gis.example.org/portal --user publisher --write
```

`create` makes a hosted feature service `exb_widget_beacon` with one table, sets its capabilities to Create only, shares it with Everyone, tags it `exb-beacon-sink`, and creates a Query only view `exb_widget_beacon_view` shared with your organization. `verify` behaves like a browser (no token) and should print `RESULT: ALL PASS`.

For ArcGIS Online use `--portal https://www.arcgis.com`. A saved profile works too: `--profile myprofile`. The password is prompted, or read from the `BEACON_PASSWORD` environment variable.

### 2. Add beacon.ts to each widget

Copy `src/beacon.ts` to `your-widget/src/shared/beacon.ts`. If you maintain several widgets, keep a master copy and copy it unchanged into each one; never edit a widget's copy.

Then wire the widget. Minimal version:

```tsx
import { beacon, type BeaconHandle } from '../shared/beacon'

// class component
private b: BeaconHandle
componentDidMount () { this.b = beacon.init(this.props) }
// function component
const b = React.useMemo(() => beacon.init(props), [props.id])

// where things happen
b.action('export-pdf', `${layout} ${orientation}`)
try { ... } catch (err) { b.error(err, 'export-pdf'); /* your own handling */ }
```

Full guidance, including how to pick action names and what not to send, is in [docs/INTEGRATION.md](docs/INTEGRATION.md). Two complete examples are in [examples/](examples/).

Rebuild the widget (`npm start` in the Experience Builder client folder) and republish or redeploy your apps. Only apps built after the change report.

### 3. Build the dashboard

```
python setup/beacon_dashboard_setup.py --portal https://gis.example.org/portal --user publisher --widgets my-widget,other-widget --write
```

`--widgets` is the comma separated list of your widgets' manifest names. The script prints the dashboard URL. See [docs/DASHBOARD.md](docs/DASHBOARD.md) for what each panel shows and how to change the layout.

### 3b. Or host the standalone dashboard

`dashboard/index.html` is a single page that reads the same view and shows what ArcGIS Dashboards cannot: sessions, an adoption matrix of widgets by app, a weekday by hour heatmap, grouped error signatures with sample stacks, and deployed versions against the latest GitHub release. Edit the `CONFIG` block at the top, drop the folder on any static web server (IIS `web.config` included), done. See [docs/STANDALONE-DASHBOARD.md](docs/STANDALONE-DASHBOARD.md).

### 4. Optional: email instead of a dashboard

```
python setup/beacon_digest.py digest --portal https://gis.example.org/portal --user publisher --to gis@example.org --widgets my-widget,other-widget --github-owner you
python setup/beacon_digest.py alert  --portal https://gis.example.org/portal --user publisher --to gis@example.org
```

`digest` is a weekly summary (events, sessions, errors against the previous week, top widgets and features, new error signatures, widgets behind their latest release). `alert` runs hourly and sends one email when a new error signature appears or a widget's error rate spikes, remembering what it already sent. Both are plain SMTP; `--dry-run` writes the HTML instead of sending. Schedule them with Task Scheduler or cron.

## Requirements and compatibility

- Experience Builder Developer Edition 1.13 or later (tested on 1.21). `beacon.ts` imports only `getAppStore` from `jimu-core`.
- Widget `tsconfig.json`: leave `jsx` alone. `beacon.ts` has no JSX and adds no dependencies.
- ArcGIS Enterprise 10.9.1 or later with a hosting server, or ArcGIS Online, for the hosted table.
- Browsers: anything current. Uses `fetch` with `keepalive` and `navigator.sendBeacon` when available.

## Cost and volume

A busy public app produces a few hundred rows a day. Each row is under 1 KB. Hosted feature layer storage on ArcGIS Online is billed by size; a year of a typical deployment is well under 100 MB. On Enterprise it lives in your hosting server's relational data store. Trim old rows with a scheduled delete if you like; the dashboard defaults to the last 30 days.

## Repository layout

```
src/beacon.ts                       the module that goes in each widget
setup/beacon_sink_setup.py          creates and locks down the table and the view
setup/beacon_dashboard_setup.py     creates or updates the ArcGIS Dashboards item
setup/beacon_digest.py              weekly email digest and hourly error alerts
dashboard/                          standalone HTML dashboard for any static web server
examples/                           a class widget and a function widget, fully wired
docs/INTEGRATION.md                 wiring a widget, naming actions, what not to send
docs/PRIVACY.md                     what is and is not collected, and why it is safe to publish the sink
docs/DASHBOARD.md                   the ArcGIS Dashboards panels, the schema note, changing the layout
docs/STANDALONE-DASHBOARD.md        hosting and configuring the HTML dashboard
docs/FAQ.md                         the questions people ask
CHANGELOG.md
LICENSE                             Apache-2.0
```

## License

Apache License 2.0. Use it, change it, ship it in your own widgets. Attribution appreciated, not required.
