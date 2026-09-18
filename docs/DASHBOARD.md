# The dashboard

`setup/beacon_dashboard_setup.py` creates an ArcGIS Dashboards item on your portal from the query only view. Run it again any time to rebuild the item in place; the script finds the existing dashboard by title and updates it.

```
python setup/beacon_dashboard_setup.py --portal https://gis.example.org/portal --user publisher --widgets my-widget,other-widget --write
```

## Panels

Header: title, subtitle, and three selectors that filter every panel.

- **Period**: last 30 days (default), last 7 days, last 24 hours, last 90 days, last year.
- **Widget**: one or more widget names.
- **App**: one or more app titles.

Row 1, indicators: events and errors for the selected period; events and errors in the last 24 hours regardless of period.

Row 2: **Activity, events per day** (the largest panel: a line binned by day), **Most used widgets** (Esri's layout and plumbing widgets such as `text`, `image`, `arcgis-map`, `controller`, `sidebar` are excluded so real tools rank), **Features used** (actions other than `open` and `loaded`, so you see which buttons people press).

Row 3: **Errors per day** and **Latest errors** (red; empty is good), **Custom widget versions in the field** (version on the axis, stacked by widget, colored per widget from the `--widgets` list), **Events by app**, **Browsers**.

## Design notes

The layout follows Esri's guidance in *Author effective dashboards* and the *Designing effective dashboards* blog: a single audience (the people who maintain the widgets), one question per panel, the most important panel largest, a muted palette with red reserved for errors, numbers with context (period next to 24 hours), and filters in the header instead of separate dashboards.

## Changing the layout

Everything is Python in `build()`. Panels are small functions (`indicator`, `bar`, `trend`, `pie`, `error_list`, `stacked_bar`) and the layout is nested `stack("row" | "col", ...)` calls. Dashboards' vocabulary is the opposite of what you might expect: a `"row"` stack lays its children out top to bottom, a `"col"` stack left to right.

Two lists are worth editing for your organization:

- `PLUMBING`: Esri widget names excluded from the popularity chart.
- `KNOWN_VALUES["action"]`: action names that get fixed colors in the pies.

## About the JSON

Dashboards has no public JSON schema. The shapes in the script were copied from items the Dashboards editor itself saved (schema `5.0.0`, Enterprise 12.1 / ArcGIS Online 2026). If Esri changes the format, open the dashboard in the editor, save once (the editor upgrades it), run the script with `--dump`, and compare `beacon_dashboard_current.json` with what `build()` produces.

Things learned the hard way, so you do not have to:

- `count_distinct` is not a valid statistic for the indicator against a hosted layer; the script uses counts only.
- A `chartRenderer` (per category colors) works on pie charts, not on serial charts. Per category bar colors are done by splitting the series (`splitBy`) on a second field, as in the versions chart. Splitting on the same field as the category fails on Enterprise 12.1.
- The value axis property `buffer: true` makes bars start above zero; the script sets it false.
- Category labels are hidden by default (`categoryAxisLabelsBehavior: "hide"` shows them on hover); the script keeps that but allows 30 characters and angles the labels 45 degrees.

## Scaling

The view is a hosted feature layer view, which is what Esri recommends for dashboards. The table has attribute indexes on `occurred_at`, `widget_name` and `action`. Relative date filters ("last 30 days") are convenient but are the one thing Esri's *Build highly scalable dashboards* page advises against for very high traffic public dashboards; this dashboard is shared with your organization only, so it is fine. If you ever open it to the public, replace the period selector with fixed dates.
