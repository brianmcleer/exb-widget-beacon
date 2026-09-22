# The standalone dashboard

`dashboard/index.html` is an alternative to the ArcGIS Dashboards item. It reads the same query only view, so nothing about the sink or the widgets changes. Use it when you want the things Dashboards cannot do against a hosted table: distinct sessions, a matrix of widgets by app, hour of day patterns, errors grouped by message, and a version check against GitHub.

It is one HTML file plus an OAuth callback page. No build, no server code, no dependencies to install. The page loads Chart.js and the ArcGIS Maps SDK from their CDNs and talks only to your portal (and, optionally, api.github.com for release tags).

## Host it

Any static web server works: IIS, nginx, Apache, an S3 bucket behind your VPN, GitHub Pages for a private repo. The folder has a `web.config` for IIS that sets the default document, short caching and a few security headers.

1. Copy `dashboard/` to the server, for example `C:\inetpub\wwwroot\widgetbeacon`.
2. Edit the `CONFIG` block at the top of the script in `index.html` (below).
3. Open it. The ArcGIS SDK asks you to sign in to the portal, because the view is shared to the organization only.

### Optional: a popup sign in

Register an application item on the portal (Content > New item > Application > Other application), add `https://<host>/<folder>/oauth-callback.html` as a redirect URI, and put its App ID in `CONFIG.oauthAppId`. The page then shows a Sign in button that opens the portal's sign in in a popup and remembers the session. Without an app id the SDK's own dialog is used, which also works.

## Configure

```js
const CONFIG = {
  portalUrl: "https://gis.example.org/portal",
  viewUrl: "",                          // FeatureServer/0 of the view, or leave empty to search by title
  viewTitle: "exb_widget_beacon_view",
  oauthAppId: "",
  orgLabel: "Example City GIS",
  logoDataUri: "",                      // optional data: URI for a small logo
  customWidgets: ["my-widget", "other-widget"],
  plumbing: [...],                      // Esri layout widgets hidden from the popularity ranking
  github: { owner: "you", repoFor: { "my-widget": "my-widget-repo" } },
  refreshMs: 300000, liveRefreshMs: 60000,
};
```

`customWidgets` drives the health table, the versions table and the "custom widgets only" toggle. `github.owner` turns on the "latest release" column; widgets not listed in `repoFor` are looked up as `<name>-widget`, and an empty string skips a widget. Release tags are read from `releases/latest` on the public GitHub API, unauthenticated, and cached in the browser for a day.

## What is on it

Six numbers with the change against the previous period of the same length: events, sessions (distinct page loads), active widgets, apps, errors, error rate per thousand events. Activity per day, switchable to errors. Most used widgets (plumbing excluded). Features used (actions other than open, loaded and error). Adoption: a heatmap of widgets by app. When people work: weekday by hour in the viewer's time zone. Versions in the field: every deployed version with its event count, colored against the latest release. Error explorer: errors grouped by their first line with numbers, ids and URLs blanked, so the same bug groups across pages, with first and last seen, affected widgets, versions, apps and browsers, and up to three sample stacks. Browsers. Widget health: a sortable table per custom widget. Latest events: the newest rows regardless of period, so you can watch a fresh deployment start reporting.

Click any bar, cell, row, chip or the errors tile to filter every panel; filters stack. Period chips or a custom range. Each card has table view, CSV and PNG export, and fullscreen. Copy link puts the whole state in the URL. Keyboard shortcuts under `?`. Auto refresh every 5 minutes, or every minute with Live. Dark mode follows the operating system or the header toggle.

## How it queries

Everything is `outStatistics` with `groupByFieldsForStatistics` against the view, about fifteen small requests per refresh, all sent together. Time bins use `EXTRACT(YEAR|MONTH|DAY|HOUR FROM occurred_at)` in the group by, which hosted services on Enterprise 10.9.1+ and ArcGIS Online support (`supportsSqlExpression`), and the browser rebuckets the UTC hours into local days. If a service rejects the expression the page falls back to one count per bin and hides the hour heatmap. Sessions are a group by `session_id` with min and max time, paged, so the page can also show median events and minutes per session. Errors are the newest 2,000 rows with `action = 'error'`, grouped in the browser.

## Changing it

The page is plain HTML, CSS and JavaScript with no framework. Colors are CSS custom properties at the top of the style block, one set for light and one for dark. Each panel is a `render*` function that reads `state.data` and draws; the queries are in `refreshAll`. Add a panel by adding a card in the markup, a query in `refreshAll` and a render function. Chart colors follow a few rules worth keeping: one hue for magnitude, red only for errors, text never in a series color, and a legend or direct labels wherever color carries identity.
