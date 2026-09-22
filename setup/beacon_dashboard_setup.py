r"""
beacon_dashboard_setup.py  -  create (or update) an ArcGIS Dashboards item for the widget beacon,
built on the query-only view that beacon_sink_setup.py created.

Panels
  Header  Period (24 h / 7 d / 30 d / 90 d / year, default 30 d), Widget and App selectors; they filter every panel.
  Row 1   indicators: events and errors for the selected period, events and errors in the last 24 hours
  Row 2   line: events per day (largest panel)   bar: most used widgets (layout widgets excluded)
          bar: features used (actions other than open and loaded)
  Row 3   red: errors per day, latest errors list; then custom widget versions in the field (stacked by widget),
          events by app, browsers
  The layout follows Esri's "Author effective dashboards": one audience, muted palette with red reserved for
  errors, size by importance, filters in the header, numbers with context.

Requires the ArcGIS API for Python (arcgis). Run (PowerShell or Command Prompt, regular):
  python beacon_dashboard_setup.py --portal https://gis.example.org/portal --user publisher --widgets my-widget,other-widget
  python beacon_dashboard_setup.py ... --write     # creates or updates the item (default is a dry run that writes the JSON to ./logs)
  python beacon_dashboard_setup.py ... --dump      # saves the live item JSON next to this script, handy after editing in the Dashboards editor

--widgets is the comma separated list of your widgets' manifest names; it drives the versions chart colors
and the "custom widgets only" filter. The Dashboards JSON schema (5.0.0) was copied from items the
Dashboards editor itself saved; if a future release changes it, open the item in the editor, save once,
run --dump and compare.

Changelog
  2026-09-18  1.3.0  Generalized for any portal. Header selectors, trend, versions stack, errors in red.
"""

import os
import sys
import json
import uuid
import getpass
import logging
import argparse
import datetime as dt

# ------------------------------------------------------------------ arguments
ap = argparse.ArgumentParser(description="Create or update the widget beacon dashboard.")
ap.add_argument("--portal", default=os.environ.get("BEACON_PORTAL", "https://www.arcgis.com"))
ap.add_argument("--user", default=os.environ.get("BEACON_USER"))
ap.add_argument("--profile", default=None, help="Saved arcgis profile instead of --portal/--user")
ap.add_argument("--view-title", default="exb_widget_beacon_view")
ap.add_argument("--title", default="Experience Builder Widget Beacon", help="Dashboard title")
ap.add_argument("--folder", default=None)
ap.add_argument("--widgets", default=os.environ.get("BEACON_WIDGETS", ""), help="Comma separated manifest names of your custom widgets")
ap.add_argument("--theme", default="dark", choices=["dark", "light"])
ap.add_argument("--write", action="store_true")
ap.add_argument("--dump", action="store_true")
args = ap.parse_args()

DRY_RUN = not args.write
PORTAL_URL = args.portal.rstrip("/")
VIEW_TITLE = args.view_title
DASH_TITLE = args.title
DASH_FOLDER = args.folder

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(os.path.join(LOG_DIR, f"beacon_dashboard_setup_{stamp}.log")), logging.StreamHandler()])
log = logging.getLogger(__name__)
log.info("DRY_RUN=%s PORTAL=%s", DRY_RUN, PORTAL_URL)


def connect():
    from arcgis.gis import GIS
    if args.profile:
        return GIS(profile=args.profile)
    if not args.user:
        raise SystemExit("Give --user (and --portal), or --profile.")
    pw = os.environ.get("BEACON_PASSWORD") or getpass.getpass(f"Password for {args.user} on {PORTAL_URL}: ")
    return GIS(PORTAL_URL, args.user, pw)


# ------------------------------------------------------------------ dashboard JSON builders (Dashboards schema 5.0.0)
# Shapes copied from an item that the Dashboards editor itself saved (run --dump to refresh the reference copy).
def _id():
    return str(uuid.uuid4())


def rel_days(n):
    return {"type": "filterRule", "field": {"name": "occurred_at", "type": "date"}, "operator": "is_within_last",
            "constraint": {"type": "relativeDate", "unit": "day", "value": n}}


ERR_RULE = {"type": "filterRule", "field": {"name": "action", "type": "string"}, "operator": "equal", "constraint": {"type": "value", "value": "error"}}
# Esri layout and plumbing widgets that every app has; they are noise in a popularity ranking.
PLUMBING = ["text", "image", "arcgis-map", "controller", "sidebar", "fixed", "navigator", "button", "card", "divider", "menu",
            "section", "views-navigation", "grid", "row", "column", "branding"]
NOT_PLUMBING = {"type": "filterRule", "field": {"name": "widget_name", "type": "string"}, "operator": "is_not_in",
                "constraint": {"type": "values", "values": PLUMBING}}
COUNT = {"onStatisticField": "objectid", "statisticType": "count", "outStatisticFieldName": "COUNT_OBJECTID"}
STATE = {"verticalAlignment": "middle", "showTopCaption": True, "showBottomCaption": True}
FONT = lambda weight="normal", angle=0: {"type": "esriTS", "angle": angle, "font": {"family": "inherit", "style": "normal", "weight": weight}}
BLUE = [20, 158, 206, 255]
RED = [216, 73, 73, 255]


def dataset(view_id, rules, stats=(), group_by=(), order_by=(), max_features=None):
    d = {"type": "serviceDataset", "name": "main", "dataSource": {"type": "layerDataSource", "itemId": view_id, "layerId": 0},
         "filter": {"type": "filterGroup", "condition": "AND", "rules": list(rules)},
         "groupByFields": list(group_by), "orderByFields": list(order_by), "statisticDefinitions": list(stats),
         "outFields": ["*"], "returnDistinctValues": False, "allowSourceDownload": False, "allowSummaryDownload": False}
    if max_features:
        d["maxFeatures"] = max_features
    return d


def base(name, wtype):
    return {"id": _id(), "name": name, "showLastUpdate": False, "noDataState": STATE, "noFilterState": STATE, "type": wtype}


def indicator(view_id, name, caption, rules):
    w = base(name, "indicatorWidget")
    w.update({"datasets": [dataset(view_id, rules, [COUNT])],
              "defaultSettings": {"topSection": {"fontSize": 60, "textInfo": {"text": name}},
                                  "middleSection": {"fontSize": 140, "textInfo": {"text": "{calculated/value}"}},
                                  "bottomSection": {"fontSize": 50, "textInfo": {"text": caption}}},
              "comparison": "none",
              "valueFormat": {"name": "value", "prefix": False, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 0},
              "percentageFormat": {"name": "percentage", "prefix": False, "style": "percent", "useGrouping": True},
              "ratioFormat": {"name": "ratio", "prefix": False, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 2},
              "valueType": "statistic", "noValueState": STATE})
    return w


def axis(category, angle=0):
    a = {"type": "chartAxis", "visible": True,
         "title": {"type": "chartText", "visible": True, "content": FONT("bold", angle)},
         "lineSymbol": {"type": "esriSLS", "style": "esriSLSSolid", "width": 1},
         "labels": {"type": "chartText", "visible": True, "content": FONT("normal", 45 if category else 0)},
         "grid": {"type": "esriSLS", "style": "esriSLSSolid", "width": 1}, "guides": []}
    if category:
        a["valueFormat"] = {"type": "category", "characterLimit": 30}
        a["scrollbar"] = {"width": 15, "gripSize": 22}
    else:
        a["valueFormat"] = {"type": "number", "intlOptions": {"style": "decimal", "notation": "standard", "minimumFractionDigits": 0, "maximumFractionDigits": 1}}
        a["buffer"] = False
    return a


def bar(view_id, name, field, rules, color=BLUE, top=15, desc=True):
    w = base(name, "serialChartWidget")
    w.update({"datasets": [dataset(view_id, rules, [COUNT], [field], ["COUNT_OBJECTID " + ("desc" if desc else "asc")], top)],
              "actionMode": "monoSelection", "categoryType": "groupByValues",
              "valueFormat": {"name": "value", "prefix": True, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 0},
              "labelFormat": {"name": "label", "prefix": True, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 0},
              "category": {"labelOverrides": [], "nullLabel": "null", "blankLabel": "blank"},
              "parseDates": False, "minPeriod": "MM", "categoryAxisLabelsBehavior": "hide",
              "chartConfig": {"version": "25.0.0", "type": "chart", "orderOptions": {}, "colorMatch": False,
                              "axes": [axis(True), axis(False, 270)],
                              "series": [{"type": "barSeries", "id": "COUNT_OBJECTID", "name": "groupByValues", "x": field, "y": "COUNT_OBJECTID",
                                          "dataLabels": {"type": "chartText", "visible": False, "content": FONT()},
                                          "dataTooltipVisible": True, "dataTooltipReverseColor": True,
                                          "fillSymbol": {"type": "esriSFS", "style": "esriSFSSolid", "color": color,
                                                         "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": color, "width": 1}}}],
                              "legend": {"type": "chartLegend", "visible": False, "body": FONT(), "position": "bottom"},
                              "horizontalAxisLabelsBehavior": "hide",
                              "cursorCrosshair": {"type": "cursorCrosshair", "verticalLineVisible": False, "horizontalLineVisible": False},
                              "stackedType": "sideBySide"}})
    return w


def trend(view_id, name, rules, color=BLUE):
    """Events per day as a line, binned by day. Shape copied from an editor-saved date chart."""
    w = base(name, "serialChartWidget")
    date_axis = axis(True)
    date_axis["labels"]["content"]["angle"] = 0
    date_axis["valueFormat"] = {"type": "date", "intlOptions": {}, "formatPerDateTimeUnit": {
        "year": {"year": "numeric"}, "month": {"month": "short"}, "day": {"day": "numeric", "month": "short"},
        "hour": {"minute": "2-digit", "hour": "2-digit", "hour12": False}, "minute": {"minute": "2-digit", "hour": "2-digit", "hour12": False},
        "second": {"second": "2-digit", "minute": "2-digit", "hour": "2-digit", "hour12": False}}}
    date_axis["tickSpacing"] = 70
    w.update({"datasets": [dataset(view_id, rules, [COUNT], ["occurred_at"], ["occurred_at ASC"])],
              "actionMode": "multiSelection", "categoryType": "groupByValues",
              "valueFormat": {"name": "value", "prefix": True, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 0},
              "labelFormat": {"name": "label", "prefix": True, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 0},
              "category": {"labelOverrides": [], "nullLabel": "null", "blankLabel": "blank"},
              "parseDates": True, "minPeriod": "DD", "categoryAxisLabelsBehavior": "hide",
              "chartConfig": {"version": "25.0.0", "type": "chart", "orderOptions": {}, "colorMatch": False,
                              "axes": [date_axis, axis(False, 270)],
                              "series": [{"type": "lineSeries", "id": "COUNT_OBJECTID", "name": "Events", "x": "occurred_at", "y": "COUNT_OBJECTID",
                                          "dataLabels": {"type": "chartText", "visible": False, "content": FONT()},
                                          "dataTooltipVisible": True, "dataTooltipReverseColor": True,
                                          "binTemporalData": True, "temporalBinning": {"size": 1, "unit": "days", "nullPolicy": "interpolate"},
                                          "lineSmoothed": False,
                                          "lineSymbol": {"type": "esriSLS", "style": "esriSLSSolid", "color": color, "width": 2},
                                          "markerVisible": True,
                                          "markerSymbol": {"type": "esriSMS", "style": "esriSMSCircle", "color": color, "size": 6,
                                                           "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": color}},
                                          "showArea": True, "areaColor": color[:3] + [60], "connectLines": True}],
                              "legend": {"type": "chartLegend", "visible": False, "body": FONT(), "position": "bottom"},
                              "horizontalAxisLabelsBehavior": "hide",
                              "cursorCrosshair": {"type": "cursorCrosshair", "verticalLineVisible": True},
                              "stackedType": "sideBySide"}})
    return w


def stacked_bar(view_id, name, field, split_field, rules, top=20, known=None, legend=True, template_color=None):
    """Category on one field, series per value of split_field (a Dashboards "split by"). Passing the same field
    for both gives every bar its own color, which is how the editor colors bars per category. Known values get
    fixed palette colors so a widget keeps its color across panels; unknown values use template_color."""
    w = bar(view_id, name, field, rules, BLUE, top)
    if split_field != field:
        w["datasets"][0]["groupByFields"] = [field, split_field]
        w["datasets"][0]["orderByFields"] = [f"{field} ASC"]
    tc = list(template_color or [214, 214, 214, 255])
    w["splitBy"] = {"fieldName": split_field, "missingSeriesTemplate": {
        "type": "barSeries", "id": "__split-by-template__", "name": "__split-by-template__", "x": field, "y": "COUNT_OBJECTID",
        "dataLabels": {"type": "chartText", "visible": False, "content": FONT()}, "dataTooltipVisible": True, "dataTooltipReverseColor": True,
        "fillSymbol": {"type": "esriSFS", "style": "esriSFSSolid", "color": tc, "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": tc, "width": 1}}}}
    series = []
    for i, v in enumerate(known if known is not None else CUSTOM_WIDGETS):
        c = PALETTE[i % len(PALETTE)] + [255]
        series.append({"type": "barSeries", "id": v, "name": v, "x": field, "y": v,
                       "dataLabels": {"type": "chartText", "visible": False, "content": FONT()}, "dataTooltipVisible": True, "dataTooltipReverseColor": True,
                       "fillSymbol": {"type": "esriSFS", "style": "esriSFSSolid", "color": c, "outline": {"type": "esriSLS", "style": "esriSLSSolid", "color": c, "width": 1}}})
    w["chartConfig"]["series"] = series
    w["chartConfig"]["stackedType"] = "stacked"
    w["chartConfig"]["legend"] = {"type": "chartLegend", "visible": legend, "body": FONT(), "position": "bottom"}
    return w


CUSTOM_WIDGETS = [w.strip() for w in (args.widgets or "").split(",") if w.strip()]   # --widgets a,b,c (manifest names)
ONLY_CUSTOM = ({"type": "filterRule", "field": {"name": "widget_name", "type": "string"}, "operator": "is_in",
                "constraint": {"type": "values", "values": CUSTOM_WIDGETS}} if CUSTOM_WIDGETS else NOT_PLUMBING)

NOT_LIFECYCLE = {"type": "filterRule", "field": {"name": "action", "type": "string"}, "operator": "is_not_in",
                 "constraint": {"type": "values", "values": ["open", "loaded", "error"]}}

PALETTE = [[20, 158, 206], [255, 170, 0], [91, 178, 89], [148, 103, 189], [255, 127, 80], [60, 180, 160], [230, 120, 180], [189, 189, 60],
           [0, 122, 194], [246, 200, 95], [140, 200, 220], [170, 110, 40], [120, 120, 200], [200, 80, 120], [90, 150, 90], [160, 160, 160]]
KNOWN_VALUES = {
    "action": ["open", "loaded", "error", "export-pdf", "export-image", "print", "search", "identify", "draw", "measure", "save", "share"],
    "browser": ["Chrome", "Edge", "Firefox", "Safari", "Other"],
}


def fill(rgb):
    return {"type": "esriSFS", "style": "esriSFSSolid", "color": list(rgb) + [255], "outline": {"type": "esriSLS", "style": "esriSLSSolid", "width": 0}}


def pie(view_id, name, field, rules):
    w = base(name, "pieChartWidget")
    grey = fill([214, 214, 214])
    infos = [{"label": v, "value": v, "symbol": fill(PALETTE[i % len(PALETTE)])} for i, v in enumerate(KNOWN_VALUES.get(field, []))]
    w.update({"datasets": [dataset(view_id, rules, [COUNT], [field], ["COUNT_OBJECTID desc"])],
              "actionMode": "monoSelection", "categoryType": "groupByValues",
              "chartConfig": {"version": "25.0.0", "type": "chart", "orderOptions": {}, "colorMatch": True,
                              "chartRenderer": {"type": "uniqueValue", "field1": field, "defaultSymbol": fill(PALETTE[len(infos) % len(PALETTE)]),
                                                "uniqueValueInfos": infos + [{"label": "null", "symbol": grey, "value": None}, {"label": "blank", "symbol": grey, "value": ""}]},
                              "series": [{"type": "pieSeries", "id": "main", "name": "main", "x": field, "y": "COUNT_OBJECTID",
                                          "dataLabels": {"type": "chartText", "visible": True, "content": FONT()},
                                          "dataTooltipVisible": True, "dataTooltipReverseColor": True, "optimizeDataLabelsOverlapping": True,
                                          "alignDataLabels": True, "innerRadius": 40, "startAngle": 270,
                                          "ticks": {"type": "pieTick", "lineSymbol": {"type": "esriSLS", "style": "esriSLSSolid", "color": [214, 214, 214, 127.5]}},
                                          "fillSymbol": grey, "dataLabelsOffset": 10,
                                          "sliceGrouping": {"sliceId": "__other-slice__", "percentageThreshold": 2, "fillSymbol": grey}}],
                              "legend": {"type": "chartLegend", "visible": True, "body": {"type": "esriTS", "angle": 0, "font": {"family": "inherit", "size": 11, "style": "normal", "weight": "normal"}},
                                         "position": "bottom", "displayPercentage": False, "displayNumericValue": True, "labelMaxWidth": 120, "valueLabelMaxWidth": 50}},
              "dataLabelsFormat": "percentage",
              "valueFormat": {"name": "value", "prefix": True, "style": "decimal", "useGrouping": True, "maximumFractionDigits": 0},
              "percentageFormat": {"name": "percentage", "prefix": False, "style": "percent", "useGrouping": True, "maximumFractionDigits": 1}})
    return w


def error_list(view_id, rules):
    w = base("Latest errors", "listWidget")
    w.update({"datasets": [dataset(view_id, rules, [], [], ["occurred_at desc"], 50)],
              "selectionMode": "single", "iconType": "symbol", "showFilter": False,
              "text": "<p><strong>{field/widget_name}</strong> {field/widget_version} in {field/app_name} <em>({field/browser})</em></p>"
                      "<p>{field/detail}</p><p>{field/error_text}</p><p><small>{field/occurred_at}</small></p>"})
    return w


def category_selector(view_id, name, field, targets):
    w = base(name, "categorySelectorWidget")
    w.update({"label": name, "events": [{"type": "selectionChanged", "actions": [{"type": "filter", "targets": [
                  {"targetId": f"{t['id']}#main", "by": "whereClause", "requiresSelection": False,
                   "fieldMap": [{"sourceName": field, "targetName": field}]} for t in targets]}]}],
              "datasets": [dataset(view_id, [], [{"onStatisticField": field, "statisticType": "count", "outStatisticFieldName": "COUNT_" + field.upper()}],
                                   [field], [f"{field} ASC"], 50)],
              "category": {"type": "groupByValues", "labelOverrides": []},
              "selection": {"operator": "equal", "allowNone": True, "noneLabelPlacement": "first", "type": "multiple", "defaultSelection": "none"},
              "showFilter": True, "displayType": "list", "maxSize": "compact", "presentationMode": "dropdown"})
    return w


def date_selector(name, targets):
    def opt(label, days):
        return {"displayName": label, "filter": {"type": "filterGroup", "condition": "OR", "rules": [{"type": "filterGroup", "condition": "AND", "rules": [
            {"type": "filterRule", "field": {"name": "filterField", "type": "date"}, "operator": "is_within_last",
             "constraint": {"type": "relativeDate", "unit": "day", "value": days}}]}]}}
    w = base(name, "dateSelectorWidget")
    w.update({"label": name, "events": [{"type": "selectionChanged", "actions": [{"type": "filter", "targets": [
                  {"targetId": f"{t['id']}#main", "by": "whereClause", "requiresSelection": False,
                   "fieldMap": [{"sourceName": "filterField", "targetName": "occurred_at"}]} for t in targets]}]}],
              "datasets": [], "optionType": "definedOptions", "presentationMode": "dropdown",
              "definedOptions": {"type": "definedOptions", "defaultSelection": "first", "noneLabelPlacement": "first", "allowNone": False,
                                 "namedFilters": [opt("Last 30 days", 30), opt("Last 7 days", 7), opt("Last 24 hours", 1), opt("Last 90 days", 90), opt("Last year", 365)],
                                 "displayType": "list", "maxSize": "compact"}})
    return w


def stack(orientation, children, width=1, height=1):
    return {"width": width, "height": height, "id": _id(), "type": "stackLayoutElement", "orientation": orientation, "elements": children}


def item(w, width, height):
    return {"width": width, "height": height, "type": "itemLayoutElement", "id": w["id"]}


def build(view_id):
    # Period comes from the header selector (default last 30 days); the two 24 h indicators keep their own window.
    none, err, d1 = [], [ERR_RULE], [rel_days(1)]
    kpis = [indicator(view_id, "Events", "selected period", none),
            indicator(view_id, "Errors", "selected period", err),
            indicator(view_id, "Events", "last 24 hours", d1),
            indicator(view_id, "Errors", "last 24 hours", d1 + [ERR_RULE])]
    activity = trend(view_id, "Activity: events per day", none)
    popular = bar(view_id, "Most used widgets (layout widgets excluded)", "widget_name", [NOT_PLUMBING])
    features = bar(view_id, "Features used (actions other than open and loaded)", "action", [NOT_LIFECYCLE], [255, 170, 0, 255])
    err_trend = trend(view_id, "Errors per day", err, RED)
    err_widgets = bar(view_id, "Errors by widget", "widget_name", err, RED, 10)
    latest = error_list(view_id, err)
    versions = stacked_bar(view_id, "Custom widget versions in the field", "widget_version", "widget_name", [ONLY_CUSTOM])
    # Which widget each recorded feature belongs to. Split by widget_name, the same split shape as the
    # versions chart, which is the one Enterprise 12.1 renders without warning triangles.
    feat_widgets = stacked_bar(view_id, "Features used, by widget", "action", "widget_name", [NOT_LIFECYCLE, ONLY_CUSTOM], 20, legend=False)
    # Ascending, so the top of this chart is what nobody opens: retirement candidates, or widgets that
    # were built and never added to an app.
    quiet = bar(view_id, "Quiet custom widgets (least used first)", "widget_name", [ONLY_CUSTOM], [140, 140, 150, 255], 10, desc=False)
    apps = bar(view_id, "Events by app", "app_name", none, [91, 178, 89, 255])
    browsers = pie(view_id, "Browsers", "browser", none)
    widgets = kpis + [activity, popular, features, err_trend, err_widgets, latest, versions, feat_widgets, quiet, apps, browsers]

    # Four bands, top to bottom: the numbers, what people use, what is broken, and the long tail.
    # A "row" stack lays its children out top to bottom; a "col" stack lays them left to right.
    layout = {"type": "dockingLayout", "rootElement": stack("row", [
        stack("col", [item(w, 0.25, 1) for w in kpis], 1, 0.13),
        stack("col", [item(activity, 0.44, 1), item(popular, 0.30, 1), item(features, 0.26, 1)], 1, 0.31),
        stack("col", [item(err_trend, 0.26, 1), item(err_widgets, 0.26, 1), item(latest, 0.48, 1)], 1, 0.30),
        stack("col", [item(versions, 0.30, 1), item(feat_widgets, 0.26, 1), item(quiet, 0.20, 1), item(apps, 0.13, 1), item(browsers, 0.11, 1)], 1, 0.26)])}

    selectors = [date_selector("Period", widgets),
                 category_selector(view_id, "Widget", "widget_name", widgets),
                 category_selector(view_id, "App", "app_name", widgets)]
    header = {"type": "header", "title": DASH_TITLE, "subtitle": "Anonymous usage and error telemetry from Experience Builder widgets",
              "subtitlePlacement": "sameLine", "logoSize": "small", "backgroundImageSizing": "fit-height",
              "normalBackgroundImagePlacement": "left", "horizontalBackgroundImagePlacement": "top",
              "showSignOutMenu": True, "showMargin": True, "menuContents": [], "selectors": selectors}

    prefixes = [("yotta", "Y", True), ("zeta", "Z", True), ("exa", "E", True), ("peta", "P", True), ("tera", "T", True), ("giga", "G", True),
                ("mega", "M", True), ("kilo", "k", True), ("base", "", True), ("deci", "d", False), ("centi", "c", False), ("milli", "m", False),
                ("micro", "\u00b5", False), ("nano", "n", False)]
    return {"version": "5.0.0", "authoringApp": "ArcGIS Dashboards", "authoringAppVersion": "5.0.0", "maxPaginationRecords": 50000,
            "maxChartRecords": 10000, "timeZone": "system", "theme": {"id": args.theme, "type": "defined"},
            "numberPrefixOverrides": [{"key": k, "symbol": sym, "enabled": e} for k, sym, e in prefixes],
            "desktopView": {"layout": layout, "type": "desktop", "widgets": widgets, "header": header,
                            "settings": {"allowElementResizing": False, "allowElementExpansion": True, "allowReset": True}},
            "elementMappings": {}}


# ------------------------------------------------------------------ main
def find(gis, title, itype):
    hits = [h for h in gis.content.search(f'title:"{title}" AND type:"{itype}"', max_items=20) if h.title == title]
    hits.sort(key=lambda h: h.modified, reverse=True)
    return hits[0] if hits else None


def main():
    gis = connect()
    view = find(gis, VIEW_TITLE, "Feature Service")
    if not view:
        raise SystemExit(f"{VIEW_TITLE} not found. Run beacon_sink_setup.py create --write first.")
    log.info("View item %s url=%s", view.id, view.url)
    existing = find(gis, DASH_TITLE, "Dashboard")

    if args.dump:
        if not existing:
            raise SystemExit("No dashboard to dump.")
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beacon_dashboard_current.json")
        open(out, "w", encoding="utf-8").write(json.dumps(existing.get_data(), indent=2))
        log.info("Dumped current dashboard JSON to %s", out)
        return

    if not CUSTOM_WIDGETS:
        log.warning("--widgets not given: the versions chart will show every widget in grey and the custom-only filter is empty.")
    data = build(view.id)

    if DRY_RUN:
        out = os.path.join(LOG_DIR, f"beacon_dashboard_{stamp}.json")
        open(out, "w", encoding="utf-8").write(json.dumps(data, indent=2))
        log.info("(dry run) dashboard JSON written to %s. Run again with --write to create or update the item.", out)
        return

    props = {"title": DASH_TITLE, "type": "Dashboard", "typeKeywords": "Dashboard, Operations Dashboard, ArcGIS Dashboards",
             "tags": "beacon, telemetry, experience builder", "snippet": "Usage and error telemetry from Experience Builder widgets.",
             "description": f"Built by beacon_dashboard_setup.py on {dt.date.today()}. Data: {VIEW_TITLE} (organization only)."}
    if existing:
        existing.update(item_properties=props, data=json.dumps(data))
        item = existing
        log.info("Updated dashboard %s", item.id)
    else:
        item = gis.content.add(item_properties={**props, "text": json.dumps(data)}, folder=DASH_FOLDER)
        log.info("Created dashboard %s", item.id)
    try:
        item.sharing.sharing_level = "ORGANIZATION"
    except Exception:
        item.share(org=True)
    url = f"{PORTAL_URL}/apps/dashboards/{item.id}"
    log.info("OPEN: %s", url)
    print(url)


if __name__ == "__main__":
    main()
