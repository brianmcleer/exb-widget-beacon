r"""
beacon_sink_setup.py  -  create and lock down the table that Experience Builder widgets post
telemetry to (see ../src/beacon.ts), plus a query-only view for your dashboard.

Works on ArcGIS Enterprise (10.9.1 or later with a hosting server) and on ArcGIS Online.
Requires the ArcGIS API for Python (arcgis). ArcGIS Pro's Python environment has it:
  C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe
or:  pip install arcgis

Modes (first argument):

  create      Creates an empty hosted feature service named exb_widget_beacon with one table
              (layer 0) using the exact lowercase field names beacon.ts sends, then a view named
              exb_widget_beacon_view (Query only, shared with your organization) for dashboards.
              Idempotent: skips whatever already exists. Finishes by running configure.

  configure   Adds the typeKeyword exb-beacon-sink to the sink item (this is how widgets find it,
              nothing is configured in any widget), shares the sink with Everyone, forces its
              capabilities to Create only, and makes the view Query only, organization only.

  verify      Plain HTTP, no token, exactly what a browser does: confirms an anonymous portal
              search finds the sink, posts one test row, confirms an anonymous query is refused,
              checks the view, then removes the test row. Prints PASS or FAIL per check.

Connection (pick one):
  --portal https://your.portal/portal --user admin_or_publisher     (password is prompted, or set BEACON_PASSWORD)
  --profile myprofile                                                (a saved arcgis profile)
  --portal https://www.arcgis.com --user you                         (ArcGIS Online)

Examples (PowerShell or Command Prompt, regular):
  python beacon_sink_setup.py create    --portal https://gis.example.org/portal --user publisher
  python beacon_sink_setup.py create    --portal https://gis.example.org/portal --user publisher --write
  python beacon_sink_setup.py verify    --portal https://gis.example.org/portal --user publisher

Without --write the script only reports what it would do. Logs go to ./logs next to this file.

Changelog
  2026-09-18  2.0.0  Hosted table + view, generalized for any portal.
"""

import os
import sys
import json
import getpass
import logging
import argparse
import datetime as dt

# ------------------------------------------------------------------ arguments
ap = argparse.ArgumentParser(description="Set up the Experience Builder widget beacon sink.")
ap.add_argument("mode", choices=["create", "configure", "verify"])
ap.add_argument("--portal", default=os.environ.get("BEACON_PORTAL", "https://www.arcgis.com"), help="Portal URL the apps load from")
ap.add_argument("--user", default=os.environ.get("BEACON_USER"), help="Publisher or admin account that will own the items")
ap.add_argument("--profile", default=None, help="Saved arcgis profile name instead of --portal/--user")
ap.add_argument("--title", default="exb_widget_beacon", help="Sink service title (default exb_widget_beacon)")
ap.add_argument("--view-title", default="exb_widget_beacon_view", help="Dashboard view title")
ap.add_argument("--folder", default=None, help="Portal folder for the items (default root)")
ap.add_argument("--write", action="store_true", help="Actually create and change things (default is a dry run)")
args = ap.parse_args()

MODE = args.mode
DRY_RUN = not args.write
PORTAL_URL = args.portal.rstrip("/")
ITEM_TITLE = args.title
VIEW_TITLE = args.view_title
ITEM_FOLDER = args.folder
BEACON_TAG = "exb-beacon-sink"      # must match BEACON_TAG in beacon.ts

# Field list. Names are lowercase on purpose: beacon.ts sends these exact keys in applyEdits.
FIELDS = [
    ("app_id",         "esriFieldTypeString", 50),
    ("app_name",       "esriFieldTypeString", 100),
    ("widget_name",    "esriFieldTypeString", 100),
    ("widget_version", "esriFieldTypeString", 20),
    ("action",         "esriFieldTypeString", 50),
    ("detail",         "esriFieldTypeString", 250),
    ("error_text",     "esriFieldTypeString", 1000),
    ("host",           "esriFieldTypeString", 100),
    ("browser",        "esriFieldTypeString", 20),
    ("session_id",     "esriFieldTypeString", 32),
    ("beacon_version", "esriFieldTypeString", 10),
    ("occurred_at",    "esriFieldTypeDate", None),
]

# ------------------------------------------------------------------ logging
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(os.path.join(LOG_DIR, f"beacon_sink_setup_{stamp}.log")), logging.StreamHandler()])
log = logging.getLogger(__name__)
log.info("MODE=%s DRY_RUN=%s PORTAL=%s", MODE, DRY_RUN, PORTAL_URL)


# ------------------------------------------------------------------ helpers
def connect():
    from arcgis.gis import GIS
    if args.profile:
        return GIS(profile=args.profile)
    if not args.user:
        raise SystemExit("Give --user (and --portal), or --profile.")
    pw = os.environ.get("BEACON_PASSWORD") or getpass.getpass(f"Password for {args.user} on {PORTAL_URL}: ")
    return GIS(PORTAL_URL, args.user, pw)


def find_item(gis, title, required=True):
    hits = gis.content.search(f'title:"{title}" AND type:"Feature Service"', max_items=20)
    hits = [h for h in hits if h.title == title]
    if not hits:
        if required:
            raise SystemExit(f"No Feature Service item titled {title}. Run: create")
        return None
    if len(hits) > 1:
        log.warning("More than one item titled %s; using the newest.", title)
        hits.sort(key=lambda h: h.modified, reverse=True)
    return hits[0]


def table_definition():
    fields = [{"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID",
               "sqlType": "sqlTypeOther", "nullable": False, "editable": False}]
    for name, ftype, length in FIELDS:
        f = {"name": name, "type": ftype, "alias": name.replace("_", " ").title(),
             "sqlType": "sqlTypeOther", "nullable": True, "editable": True}
        if length:
            f["length"] = length
        fields.append(f)
    return {
        "id": 0, "name": ITEM_TITLE, "type": "Table", "displayField": "widget_name",
        "description": "Anonymous usage and error telemetry from Experience Builder widgets (beacon.ts).",
        "objectIdField": "OBJECTID", "fields": fields,
        "indexes": [{"name": "PK_OBJECTID", "fields": "OBJECTID", "isUnique": True, "isAscending": True},
                    {"name": "IX_OCCURRED", "fields": "occurred_at", "isUnique": False, "isAscending": True},
                    {"name": "IX_WIDGET", "fields": "widget_name", "isUnique": False, "isAscending": True},
                    {"name": "IX_ACTION", "fields": "action", "isUnique": False, "isAscending": True}],
        "capabilities": "Create", "hasAttachments": False, "allowGeometryUpdates": False,
        "supportsApplyEditsWithGlobalIds": False,
    }


def set_caps(flc, caps):
    if flc.properties.get("capabilities", "") != caps:
        log.info("  service capabilities %s -> %s", flc.properties.get("capabilities", ""), caps)
        if not DRY_RUN:
            flc.manager.update_definition({"capabilities": caps})
    for lyr in list(flc.layers) + list(flc.tables):
        if lyr.properties.get("capabilities", "") != caps:
            log.info("  layer %s capabilities %s -> %s", lyr.properties.get("id"), lyr.properties.get("capabilities", ""), caps)
            if not DRY_RUN:
                lyr.manager.update_definition({"capabilities": caps})


def share(item, everyone):
    """Share with Everyone (public) or with the organization only, across arcgis API versions."""
    if DRY_RUN:
        return
    try:
        item.sharing.sharing_level = "EVERYONE" if everyone else "ORGANIZATION"
    except Exception:
        item.share(everyone=everyone, org=True)


# ------------------------------------------------------------------ create
def create():
    import time
    from arcgis.features import FeatureLayerCollection
    gis = connect()
    item = find_item(gis, ITEM_TITLE, required=False)
    if item:
        log.info("Sink exists: %s (%s)", item.title, item.id)
    else:
        log.info("Creating empty hosted feature service %s", ITEM_TITLE)
        if DRY_RUN:
            log.info("  (dry run) would create the service, add the table and create the view; rerun with --write")
            return
        item = gis.content.create_service(name=ITEM_TITLE, service_type="featureService", has_static_data=False,
                                          capabilities="Create", tags="beacon, telemetry, experience builder",
                                          snippet="Sink for Experience Builder widget usage and error telemetry. Add only.",
                                          folder=ITEM_FOLDER)
        log.info("  created item %s", item.id)
        time.sleep(3)
        flc = FeatureLayerCollection.fromitem(item)
        log.info("  add_to_definition: %s", flc.manager.add_to_definition({"tables": [table_definition()]}))
        time.sleep(3)
        item = gis.content.get(item.id)

    flc = FeatureLayerCollection.fromitem(item)
    if not flc.tables and not flc.layers:
        log.info("Service has no table yet; adding")
        if not DRY_RUN:
            log.info("  add_to_definition: %s", flc.manager.add_to_definition({"tables": [table_definition()]}))
            flc = FeatureLayerCollection.fromitem(gis.content.get(item.id))

    view = find_item(gis, VIEW_TITLE, required=False)
    if view:
        log.info("View exists: %s (%s)", view.title, view.id)
    else:
        log.info("Creating view %s (Query only, organization)", VIEW_TITLE)
        if not DRY_RUN:
            view = flc.manager.create_view(name=VIEW_TITLE, capabilities="Query", allow_schema_changes=False,
                                           updateable=False, folder=ITEM_FOLDER)
            view.update(item_properties={"snippet": "Query-only view of the beacon sink for dashboards. Not public.",
                                         "tags": "beacon, telemetry, experience builder"})
            log.info("  created view %s", view.id)
    configure(gis)


# ------------------------------------------------------------------ configure
def configure(gis=None):
    from arcgis.features import FeatureLayerCollection
    gis = gis or connect()
    item = find_item(gis, ITEM_TITLE)
    log.info("Sink %s (%s) url=%s", item.title, item.id, item.url)
    keywords = list(item.typeKeywords or [])
    if BEACON_TAG not in keywords:
        log.info("  adding typeKeyword %s", BEACON_TAG)
        if not DRY_RUN:
            item.update(item_properties={"typeKeywords": keywords + [BEACON_TAG]})
    else:
        log.info("  typeKeyword already present")
    log.info("  sharing with Everyone")
    share(item, everyone=True)
    set_caps(FeatureLayerCollection.fromitem(item), "Create")

    view = find_item(gis, VIEW_TITLE, required=False)
    if view:
        log.info("View %s (%s) url=%s", view.title, view.id, view.url)
        log.info("  sharing with the organization only")
        share(view, everyone=False)
        set_caps(FeatureLayerCollection.fromitem(view), "Query")
    else:
        log.warning("View %s not found; the dashboard needs it. Run: create", VIEW_TITLE)
    log.info("Done. Widgets loaded from %s find the sink on their next page load. Run: verify", PORTAL_URL)


# ------------------------------------------------------------------ verify
def verify():
    import requests
    from arcgis.features import FeatureLayerCollection
    gis = connect()
    item = find_item(gis, ITEM_TITLE)
    layer_url = item.url.rstrip("/") + "/0"
    ok = True

    r = requests.get(f"{PORTAL_URL}/sharing/rest/search", params={"f": "json", "num": 1, "q": f'typekeywords:"{BEACON_TAG}"'}, timeout=30)
    found = r.json().get("results", [])
    res = bool(found) and found[0].get("url", "").rstrip("/") == item.url.rstrip("/")
    log.info("%s anonymous portal search finds the sink", "PASS" if res else "FAIL"); ok &= res

    row = {"attributes": {"app_id": "verify", "app_name": "beacon_sink_setup", "widget_name": "verify", "widget_version": "0",
                          "action": "verify", "detail": "", "error_text": "", "host": "script", "browser": "Other",
                          "session_id": stamp, "beacon_version": "0.0.0", "occurred_at": int(dt.datetime.now().timestamp() * 1000)}}
    r = requests.post(f"{layer_url}/applyEdits", data={"f": "json", "rollbackOnFailure": "false", "adds": json.dumps([row])}, timeout=30)
    j = r.json()
    add = (j.get("addResults") or [{}])[0]
    res = bool(add.get("success"))
    log.info("%s anonymous applyEdits add (%s)", "PASS" if res else "FAIL", j if not res else add.get("objectId")); ok &= res

    r = requests.get(f"{layer_url}/query", params={"f": "json", "where": "1=1", "returnCountOnly": "true"}, timeout=30)
    res = "error" in r.json()
    log.info("%s anonymous query refused (%s)", "PASS" if res else "FAIL", r.json().get("error", {}).get("message", r.json())); ok &= res

    view = find_item(gis, VIEW_TITLE, required=False)
    if view:
        vcaps = FeatureLayerCollection.fromitem(view).properties.get("capabilities", "")
        res = vcaps == "Query" and view.access != "public"
        log.info("%s view is Query only and not public (caps=%s access=%s)", "PASS" if res else "FAIL", vcaps, view.access); ok &= res
    else:
        log.info("FAIL view %s missing", VIEW_TITLE); ok = False

    if add.get("objectId") is not None and not DRY_RUN:
        flc = FeatureLayerCollection.fromitem(item)
        tbl = (list(flc.tables) + list(flc.layers))[0]
        flc.manager.update_definition({"capabilities": "Create,Query,Delete"})
        tbl.manager.update_definition({"capabilities": "Create,Query,Delete"})
        log.info("cleanup delete: %s", tbl.delete_features(where=f"session_id = '{stamp}'"))
        set_caps(FeatureLayerCollection.fromitem(gis.content.get(item.id)), "Create")
    elif add.get("objectId") is not None:
        log.info("test row %s left in place (dry run); rerun verify with --write to clean it up", add.get("objectId"))

    log.info("RESULT: %s", "ALL PASS" if ok else "SOMETHING FAILED, see above")


if __name__ == "__main__":
    {"create": create, "configure": configure, "verify": verify}[MODE]()
