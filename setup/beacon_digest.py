r"""
beacon_digest.py

Emails what the Widget Beacon dashboard shows, so nobody has to open it.

  digest   A weekly summary: events, sessions, errors and error rate against the previous week,
           the most used widgets and features, errors by widget, error signatures that are new this
           week, and custom widgets running behind their latest GitHub release.
  alert    An hourly check. Sends one email when a new error signature appears (not seen in the
           previous 30 days) or a widget's error rate in the last hour crosses a threshold. Remembers
           what it has already alerted on in a small state file so you get one email per problem.

Both modes read the query only view that beacon_sink_setup.py created. Nothing is written to the
portal. Email goes through a plain SMTP relay; there is no authentication code here, add it in
send_mail() if your relay needs it.

Run (any Python with the ArcGIS API for Python; the ArcGIS Pro conda environment has it):
  python beacon_digest.py digest --portal https://gis.example.org/portal --user publisher --to gis@example.org
  python beacon_digest.py alert  --portal https://gis.example.org/portal --profile myprofile --to gis@example.org
  python beacon_digest.py digest ... --dry-run          # writes the HTML next to the log, sends nothing
  python beacon_digest.py digest ... --preview out.html # writes the HTML to a file, sends nothing

Schedule digest weekly (Monday 07:00) and alert hourly with Task Scheduler or cron.

Changelog
  2026-09-18  1.0.0  First version.
"""
import argparse
import datetime as dt
import html
import json
import logging
import os
import re
import smtplib
import sys
from collections import defaultdict
from email.message import EmailMessage
from email.utils import formatdate

# ------------------------------------------------------------------ defaults (all overridable on the command line)
DEFAULTS = {
    "portal": "",
    "user": "",
    "profile": "",
    "view_title": "exb_widget_beacon_view",
    "view_url": "",
    "smtp": "localhost",
    "smtp_port": 25,
    "sender": "gis-noreply@example.org",
    "to": "",
    "dashboard_url": "",                  # link at the bottom of the email
    "org_label": "GIS",
    "custom_widgets": [],                 # manifest names; empty = everything that is not plumbing
    "github_owner": "",                   # for the "behind latest release" section
    "github_repo_for": {},                # widget -> repo, when it is not <widget>-widget
    "plumbing": ["text", "image", "arcgis-map", "controller", "sidebar", "fixed", "navigator", "button", "card",
                 "divider", "menu", "section", "views-navigation", "grid", "row", "column", "branding"],
    "lifecycle": ["open", "loaded", "error"],
    "alert_rate_per_1k": 20,              # error rate in the last hour that triggers an alert
    "alert_min_errors": 5,                # and at least this many errors, so one bad session does not page you
    "state_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"),
    "brand": {"blue1": "#0083bd", "blue2": "#003a55", "green": "#69812d", "red": "#d83b01", "text": "#1a1f24", "muted": "#6b757d", "bg": "#f5f7f9", "border": "#d8dde2"},
}

# ------------------------------------------------------------------ args
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("mode", choices=["digest", "alert"])
ap.add_argument("--portal", default=DEFAULTS["portal"])
ap.add_argument("--user", default=DEFAULTS["user"])
ap.add_argument("--password", default=os.environ.get("BEACON_PORTAL_PASSWORD", ""))
ap.add_argument("--profile", default=DEFAULTS["profile"], help="ArcGIS API for Python stored profile")
ap.add_argument("--view-url", default=DEFAULTS["view_url"])
ap.add_argument("--view-title", default=DEFAULTS["view_title"])
ap.add_argument("--smtp", default=DEFAULTS["smtp"])
ap.add_argument("--smtp-port", type=int, default=DEFAULTS["smtp_port"])
ap.add_argument("--sender", default=DEFAULTS["sender"])
ap.add_argument("--to", default=DEFAULTS["to"], help="comma separated")
ap.add_argument("--dashboard-url", default=DEFAULTS["dashboard_url"])
ap.add_argument("--org", default=DEFAULTS["org_label"])
ap.add_argument("--widgets", default=",".join(DEFAULTS["custom_widgets"]), help="comma separated custom widget names")
ap.add_argument("--github-owner", default=DEFAULTS["github_owner"])
ap.add_argument("--days", type=int, default=7, help="digest window in days")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--preview", default="", help="write the HTML here and do not send")
args = ap.parse_args()

CUSTOM = [w.strip() for w in args.widgets.split(",") if w.strip()]
B = DEFAULTS["brand"]
os.makedirs(DEFAULTS["state_dir"], exist_ok=True)
stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(os.path.join(DEFAULTS["state_dir"], f"beacon_digest_{stamp}.log")), logging.StreamHandler()])
log = logging.getLogger(__name__)


# ------------------------------------------------------------------ portal
def connect():
    from arcgis.gis import GIS
    if args.profile:
        return GIS(profile=args.profile)
    if not args.user:
        return GIS(args.portal)
    return GIS(args.portal, args.user, args.password or None)


def find_view(gis):
    from arcgis.features import FeatureLayer
    if args.view_url:
        return FeatureLayer(args.view_url, gis)
    hits = [i for i in gis.content.search(f'title:"{args.view_title}" AND type:"Feature Service"', max_items=20) if i.title == args.view_title]
    if not hits:
        raise SystemExit(f'No item titled "{args.view_title}" on {args.portal}')
    item = hits[0]
    return (item.tables or item.layers)[0]


def sql_ts(d):
    return "timestamp '" + d.strftime("%Y-%m-%d %H:%M:%S") + "'"


def q(s):
    return "'" + s.replace("'", "''") + "'"


def where(start, end=None, extra=()):
    parts = [f"occurred_at >= {sql_ts(start)}"]
    if end:
        parts.append(f"occurred_at < {sql_ts(end)}")
    parts.extend(extra)
    return " AND ".join(parts)


def count(layer, w):
    return layer.query(where=w, return_count_only=True)


def group(layer, w, fields, stats=None, order=None, num=2000):
    """Group by with a count (and optional extra statistics). Returns a list of dicts."""
    out_stats = [{"statisticType": "count", "onStatisticField": layer.properties.objectIdField, "outStatisticFieldName": "n"}] + list(stats or [])
    fs = layer.query(where=w, out_statistics=out_stats, group_by_fields_for_statistics=",".join(fields),
                     order_by_fields=order or "n DESC", result_record_count=num, return_geometry=False)
    return [f.attributes for f in fs.features]


def distinct_count(layer, w, field):
    fs = layer.query(where=w, out_fields=field, return_distinct_values=True, return_geometry=False, result_record_count=100000)
    return len(fs.features)


def signature(text):
    s = (text or "").split("\n")[0].strip()
    s = re.sub(r"https?://\S+", "<url>", s)
    s = re.sub(r"\b[0-9a-f]{16,}\b", "<id>", s, flags=re.I)
    s = re.sub(r"\b\d+(\.\d+)?\b", "#", s)
    return s[:200] or "(no message)"


def error_groups(layer, w, num=2000):
    fs = layer.query(where=w + " AND action = 'error'", out_fields="widget_name,widget_version,app_name,browser,error_text,detail,occurred_at",
                     order_by_fields="occurred_at DESC", result_record_count=num, return_geometry=False)
    groups = {}
    for f in fs.features:
        a = f.attributes
        k = signature(a.get("error_text") or a.get("detail"))
        g = groups.setdefault(k, {"sig": k, "n": 0, "widgets": defaultdict(int), "versions": set(), "apps": set(), "first": a["occurred_at"], "last": a["occurred_at"], "sample": a.get("error_text") or ""})
        g["n"] += 1
        g["widgets"][a.get("widget_name")] += 1
        if a.get("widget_version"):
            g["versions"].add(a["widget_version"])
        if a.get("app_name"):
            g["apps"].add(a["app_name"])
        g["first"] = min(g["first"], a["occurred_at"])
        g["last"] = max(g["last"], a["occurred_at"])
    return sorted(groups.values(), key=lambda g: -g["n"])


def github_latest():
    """widget -> latest release tag, via the public API. Silent on any failure."""
    if not args.github_owner or not CUSTOM:
        return {}
    import urllib.request
    out = {}
    for w in CUSTOM:
        repo = DEFAULTS["github_repo_for"].get(w, f"{w}-widget")
        if not repo:
            continue
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{args.github_owner}/{repo}/releases/latest", headers={"Accept": "application/vnd.github+json", "User-Agent": "beacon-digest"})
            with urllib.request.urlopen(req, timeout=10) as r:
                out[w] = json.load(r).get("tag_name", "").lstrip("vV")
        except Exception as e:  # 404 = no release; rate limit; offline
            log.debug("github %s: %s", repo, e)
    return out


def cmp_ver(a, b):
    pa = re.split(r"[.\-+]", str(a).lstrip("vV")); pb = re.split(r"[.\-+]", str(b).lstrip("vV"))
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else "0"; y = pb[i] if i < len(pb) else "0"
        if x.isdigit() and y.isdigit():
            if int(x) != int(y):
                return int(x) - int(y)
        elif x != y:
            return -1 if x < y else 1
    return 0


# ------------------------------------------------------------------ HTML (email safe: tables, inline styles, Arial)
def fmt(n):
    return "–" if n is None else f"{int(round(n)):,}"


def delta(cur, prev, invert=False):
    if prev in (None, 0):
        return ""
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.5:
        return f'<span style="color:{B["muted"]}">±0%</span>'
    good = (pct < 0) if invert else (pct > 0)
    return f'<span style="color:{B["green"] if good else B["red"]};font-weight:bold">{"▲" if pct > 0 else "▼"} {abs(pct):.0f}%</span>'


def kpi(label, value, sub=""):
    return (f'<td width="16%" style="padding:10px 12px;background:#fff;border:1px solid {B["border"]};border-radius:4px;vertical-align:top">'
            f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{B["muted"]}">{html.escape(label)}</div>'
            f'<div style="font-size:26px;font-weight:bold;color:{B["text"]};line-height:1.1;margin:4px 0">{value}</div>'
            f'<div style="font-size:12px;color:{B["muted"]}">{sub}</div></td>')


def section(title, body, sub=""):
    return (f'<h2 style="font-size:14px;margin:22px 0 6px;color:{B["blue2"]}">{html.escape(title)}'
            + (f' <span style="font-weight:normal;color:{B["muted"]};font-size:12px">{html.escape(sub)}</span>' if sub else "") + "</h2>" + body)


def bars(rows, key, maxn=None, color=None):
    if not rows:
        return f'<p style="color:{B["muted"]};font-size:12px;margin:4px 0">Nothing in this period.</p>'
    maxn = maxn or max(r["n"] for r in rows) or 1
    out = [f'<table cellspacing="0" cellpadding="0" style="font-size:12px;width:100%">']
    for r in rows:
        w = max(2, int(r["n"] / maxn * 220))
        out.append(f'<tr><td style="padding:2px 8px 2px 0;white-space:nowrap;color:{B["text"]}">{html.escape(str(r[key]))}</td>'
                   f'<td style="padding:2px 0;width:100%"><div style="display:inline-block;height:10px;width:{w}px;background:{color or B["blue1"]};border-radius:2px;vertical-align:middle"></div>'
                   f' <span style="color:{B["muted"]}">{fmt(r["n"])}</span></td></tr>')
    out.append("</table>")
    return "".join(out)


def page(title, subtitle, inner):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title></head>
<body style="margin:0;padding:0;background:{B['bg']};font-family:Arial,Helvetica,sans-serif;color:{B['text']}">
<table width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:18px 8px">
<table width="720" cellspacing="0" cellpadding="0" style="max-width:720px;width:100%">
<tr><td style="background:{B['blue2']};color:#fff;padding:14px 18px;border-radius:4px 4px 0 0">
  <div style="font-size:17px;font-weight:bold">{html.escape(title)}</div>
  <div style="font-size:12px;opacity:.8;margin-top:2px">{html.escape(subtitle)}</div></td></tr>
<tr><td style="background:#fff;padding:16px 18px;border:1px solid {B['border']};border-top:0;border-radius:0 0 4px 4px">{inner}
  <p style="font-size:11px;color:{B['muted']};margin:24px 0 0;border-top:1px solid {B['border']};padding-top:8px">
  Widget Beacon · anonymous usage and error telemetry from Experience Builder widgets · generated {html.escape(dt.datetime.now().strftime('%Y-%m-%d %H:%M'))}
  {(' · <a href="' + html.escape(args.dashboard_url) + '" style="color:' + B['blue1'] + '">Open the dashboard</a>') if args.dashboard_url else ''}</p>
</td></tr></table></td></tr></table></body></html>"""


def send_mail(subject, html_body, text_body):
    if args.preview:
        open(args.preview, "w", encoding="utf-8").write(html_body)
        log.info("Preview written to %s (not sent)", args.preview)
        return
    if args.dry_run or not args.to:
        out = os.path.join(DEFAULTS["state_dir"], f"beacon_{args.mode}_{stamp}.html")
        open(out, "w", encoding="utf-8").write(html_body)
        log.info("(dry run%s) HTML written to %s", "" if args.to else ", no --to", out)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = args.sender
    msg["To"] = args.to
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(args.smtp, args.smtp_port, timeout=30) as s:
        s.send_message(msg)
    log.info("Sent '%s' to %s", subject, args.to)


# ------------------------------------------------------------------ digest
def digest(layer):
    now = dt.datetime.utcnow()
    start = now - dt.timedelta(days=args.days)
    prev_start = start - dt.timedelta(days=args.days)
    W, Wp = where(start), where(prev_start, start)
    not_plumbing = f"widget_name NOT IN ({','.join(q(p) for p in DEFAULTS['plumbing'])})"
    not_lifecycle = f"action NOT IN ({','.join(q(a) for a in DEFAULTS['lifecycle'])})"
    only_custom = f"widget_name IN ({','.join(q(w) for w in CUSTOM)})" if CUSTOM else not_plumbing

    total, prev_total = count(layer, W), count(layer, Wp)
    errors, prev_errors = count(layer, W + " AND action = 'error'"), count(layer, Wp + " AND action = 'error'")
    sessions, prev_sessions = distinct_count(layer, W, "session_id"), distinct_count(layer, Wp, "session_id")
    by_widget = group(layer, W + " AND " + not_plumbing, ["widget_name"], num=10)
    by_feature = group(layer, W + " AND " + not_lifecycle, ["action"], num=10)
    by_app = group(layer, W, ["app_name"], num=10)
    err_widget = group(layer, W + " AND action = 'error'", ["widget_name"], num=10)
    versions = group(layer, W + " AND " + only_custom, ["widget_name", "widget_version"], order="widget_name ASC", num=500)
    groups_now = error_groups(layer, W)
    seen_before = {g["sig"] for g in error_groups(layer, where(now - dt.timedelta(days=30), start))}
    new_sigs = [g for g in groups_now if g["sig"] not in seen_before]
    latest = github_latest()
    rate = errors / total * 1000 if total else 0
    prev_rate = prev_errors / prev_total * 1000 if prev_total else 0

    # versions behind
    behind = []
    per_widget = defaultdict(list)
    for r in versions:
        per_widget[r["widget_name"]].append((r["widget_version"] or "?", r["n"]))
    for w, vs in per_widget.items():
        lt = latest.get(w)
        if not lt:
            continue
        old = [(v, n) for v, n in vs if cmp_ver(v, lt) < 0]
        if old:
            tot = sum(n for _, n in vs)
            behind.append({"widget": w, "latest": lt, "old": ", ".join(f"{v} ({fmt(n)})" for v, n in sorted(old, key=lambda x: -x[1])), "pct": sum(n for _, n in old) / tot * 100})
    behind.sort(key=lambda b: -b["pct"])

    period = f"last {args.days} days" if args.days != 7 else "last 7 days"
    inner = ['<table width="100%" cellspacing="6" cellpadding="0"><tr>',
             kpi("Events", fmt(total), delta(total, prev_total) + f' vs prior {args.days} d'),
             kpi("Sessions", fmt(sessions), delta(sessions, prev_sessions) + " page loads"),
             kpi("Apps", fmt(len(by_app)), "reporting"),
             kpi("Errors", f'<span style="color:{B["red"] if errors else B["text"]}">{fmt(errors)}</span>', delta(errors, prev_errors, invert=True)),
             kpi("Error rate", f"{rate:.1f}", delta(rate, prev_rate, invert=True) + " per 1,000"),
             kpi("New errors", f'<span style="color:{B["red"] if new_sigs else B["green"]}">{len(new_sigs)}</span>', "signatures not seen in 30 d"),
             "</tr></table>"]
    inner.append(section("Most used widgets", bars(by_widget, "widget_name"), "layout widgets excluded"))
    inner.append(section("Features used", bars(by_feature, "action"), "actions other than open and loaded"))
    if err_widget:
        inner.append(section("Errors by widget", bars(err_widget, "widget_name", color=B["red"])))
    if new_sigs:
        rows = "".join(f'<tr><td style="padding:6px 8px;border-top:1px solid {B["border"]};font-weight:bold;color:{B["red"]}">{fmt(g["n"])}</td>'
                       f'<td style="padding:6px 8px;border-top:1px solid {B["border"]};font-family:Consolas,monospace;font-size:11px">{html.escape(g["sig"])}'
                       f'<div style="font-family:Arial;font-size:11px;color:{B["muted"]};margin-top:3px">{html.escape(", ".join(sorted(g["widgets"], key=lambda k: -g["widgets"][k])))}'
                       f' · {html.escape(", ".join(sorted(g["versions"])))} · {html.escape(", ".join(sorted(g["apps"])))}</div></td></tr>' for g in new_sigs[:12])
        inner.append(section("New error signatures", f'<table cellspacing="0" cellpadding="0" style="width:100%;font-size:12px">{rows}</table>', f"{len(new_sigs)} this period"))
    if behind:
        rows = "".join(f'<tr><td style="padding:6px 8px;border-top:1px solid {B["border"]};font-weight:bold">{html.escape(b["widget"])}</td>'
                       f'<td style="padding:6px 8px;border-top:1px solid {B["border"]};font-family:Consolas,monospace;font-size:11px">{html.escape(b["old"])}</td>'
                       f'<td style="padding:6px 8px;border-top:1px solid {B["border"]};font-family:Consolas,monospace;font-size:11px;color:{B["green"]}">{html.escape(b["latest"])}</td>'
                       f'<td style="padding:6px 8px;border-top:1px solid {B["border"]};color:{B["red"] if b["pct"] > 50 else B["muted"]}">{b["pct"]:.0f}% old</td></tr>' for b in behind)
        inner.append(section("Widgets behind the latest release", f'<table cellspacing="0" cellpadding="0" style="width:100%;font-size:12px"><tr style="color:{B["muted"]};font-size:11px;text-transform:uppercase"><td style="padding:4px 8px">Widget</td><td style="padding:4px 8px">Deployed (events)</td><td style="padding:4px 8px">Latest</td><td></td></tr>{rows}</table>', "republish the apps that still run the old build"))
    inner.append(section("Events by app", bars(by_app, "app_name", color=B["green"])))

    title = f"Widget Beacon weekly: {fmt(total)} events, {fmt(errors)} errors"
    text = f"{title}\n{period}\nEvents {fmt(total)} (prev {fmt(prev_total)}), sessions {fmt(sessions)}, errors {fmt(errors)}, rate {rate:.1f}/1k, new error signatures {len(new_sigs)}.\n" + (args.dashboard_url or "")
    send_mail(title, page("Widget Beacon weekly digest", f"{args.org} · {period} · {start.strftime('%b %d')} to {now.strftime('%b %d, %Y')}", "".join(inner)), text)


# ------------------------------------------------------------------ alert
def alert(layer):
    state_path = os.path.join(DEFAULTS["state_dir"], "beacon_alert_state.json")
    try:
        state = json.load(open(state_path, encoding="utf-8"))
    except Exception:
        state = {"alerted": {}}
    now = dt.datetime.utcnow()
    hour_ago = now - dt.timedelta(hours=1)
    # forget alerts older than 7 days so a recurring bug can page again
    state["alerted"] = {k: v for k, v in state["alerted"].items() if now.timestamp() - v < 7 * 86400}

    W = where(hour_ago)
    total = count(layer, W)
    groups = error_groups(layer, W, num=500)
    findings = []
    if groups:
        seen = {g["sig"] for g in error_groups(layer, where(now - dt.timedelta(days=30), hour_ago))}
        for g in groups:
            key = "sig:" + g["sig"]
            if g["sig"] not in seen and key not in state["alerted"]:
                findings.append(("New error signature", g))
                state["alerted"][key] = now.timestamp()
        # per widget rate
        by_w = group(layer, W, ["widget_name"], num=500)
        err_w = {r["widget_name"]: r["n"] for r in group(layer, W + " AND action = 'error'", ["widget_name"], num=500)}
        for r in by_w:
            e = err_w.get(r["widget_name"], 0)
            rate = e / r["n"] * 1000 if r["n"] else 0
            key = "rate:" + str(r["widget_name"])
            if e >= DEFAULTS["alert_min_errors"] and rate >= DEFAULTS["alert_rate_per_1k"] and key not in state["alerted"]:
                findings.append(("High error rate", {"sig": f'{r["widget_name"]}: {e} errors in {r["n"]} events ({rate:.0f} per 1,000) in the last hour', "n": e, "widgets": {r["widget_name"]: e}, "versions": set(), "apps": set(), "sample": ""}))
                state["alerted"][key] = now.timestamp()
    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=1)
    if not findings:
        log.info("No new problems in the last hour (%s events, %s error groups)", total, len(groups))
        return
    rows = []
    for kind, g in findings:
        rows.append(f'<div style="border-left:3px solid {B["red"]};padding:8px 10px;margin:8px 0;background:#fff8f5">'
                    f'<div style="font-size:11px;color:{B["muted"]};text-transform:uppercase;letter-spacing:.05em">{html.escape(kind)} · {fmt(g["n"])} in the last hour</div>'
                    f'<div style="font-family:Consolas,monospace;font-size:12px;margin:4px 0;color:{B["text"]}">{html.escape(g["sig"])}</div>'
                    f'<div style="font-size:11px;color:{B["muted"]}">{html.escape(", ".join(sorted(g["widgets"], key=lambda k: -g["widgets"][k])))}'
                    + (f' · {html.escape(", ".join(sorted(g["versions"])))}' if g["versions"] else "") + (f' · {html.escape(", ".join(sorted(g["apps"])))}' if g["apps"] else "") + "</div>"
                    + (f'<pre style="font-size:11px;color:{B["muted"]};white-space:pre-wrap;margin:6px 0 0;max-height:160px;overflow:hidden">{html.escape(g["sample"][:1200])}</pre>' if g["sample"] else "") + "</div>")
    title = f"Widget Beacon alert: {len(findings)} new problem{'s' if len(findings) != 1 else ''}"
    text = title + "\n\n" + "\n".join(f"{k}: {g['sig']}" for k, g in findings) + "\n" + (args.dashboard_url or "")
    send_mail(title, page("Widget Beacon alert", f"{args.org} · last hour · {hour_ago.strftime('%H:%M')} to {now.strftime('%H:%M')} UTC", "".join(rows)), text)


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    gis = connect()
    layer = find_view(gis)
    log.info("mode=%s view=%s", args.mode, layer.url)
    (digest if args.mode == "digest" else alert)(layer)
