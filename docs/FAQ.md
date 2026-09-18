# Frequently asked questions

**Does this send data to the author of this repository?**
No. There is no URL in the code. The module looks for a table on the portal that served the app, and only your organization can publish that table. If you install a widget containing `beacon.ts` and never run the setup script, nothing is sent anywhere.

**Is it GDPR / CCPA / public records safe?**
It collects no personal data: no usernames, IPs, locations, search terms or feature values, and the session id is random per page load and never persisted. See PRIVACY.md. Your own review still applies; the document is written so you can hand it over.

**Why a public, editable feature service? Is that not dangerous?**
The service accepts adds only; query, update, delete and attachments are off, and the setup script verifies that anonymously. The worst an outsider can do is add junk rows, which is the same exposure as any public survey or crowdsourcing layer, and the data is only readable through the organization only view. If you prefer, keep the table Everyone shared but put the apps and the table behind the same web tier authentication; the widget sends whatever credentials the browser already has to the portal (`credentials: 'omit'` on the fetch means it does not attach cookies, so for a web tier protected sink change that line to `'include'`).

**Can I use it on ArcGIS Online?**
Yes. `--portal https://www.arcgis.com`. Hosted feature layer storage counts toward credits; a year of a typical deployment is tens of megabytes.

**Do I need Experience Builder Developer Edition?**
Yes, to add a file to a widget. The apps themselves can be published anywhere the widgets run.

**Which Experience Builder versions?**
Tested on 1.21. The module imports only `getAppStore` from `jimu-core` and uses no JSX, so it should work on 1.13 and later. It relies on `appConfig.widgets[id].uri`, `manifest.name`, `manifest.version` and `widgetsRuntimeInfo[id].state` for the Esri widget counting; if a future release renames those, only the Esri widget rows are affected.

**Why do I see `loaded` and `open` rows for Esri widgets I never touched?**
`loaded` is recorded once per page load for every Esri widget in the app, so you can see which widgets exist in each app. `open` is recorded when a widget's runtime state becomes OPENED, which for widgets that are always visible happens at load. Compare `open` counts between widgets in the same controller for meaningful numbers.

**Why nothing in "Features used"?**
Only actions you record with `b.action(...)` show there. Fresh installs report only `open` and `loaded` until the widgets that call `action` are redeployed.

**The dashboard shows "No data" in the error panels.**
Good. That means no errors were reported in the selected period.

**Can two organizations share a table?**
Not with the portal lookup, which is by design. Each organization publishes its own sink on its own portal.

**Can I add fields?**
Yes, but add them to both the table (setup script `FIELDS`) and the event in `beacon.ts` (`BeaconEvent` and `record`). Keep names lowercase; the feature service matches attribute names exactly as sent.

**What happens if the table is unreachable?**
Nothing visible. The lookup result (including "none") is cached for the session, posts are fire and forget, and every path is wrapped in try/catch. Widgets never wait on telemetry.

**How do I turn it off for one app?**
Set `"telemetry": false` in that widget's config in the app (or expose the checkbox described in INTEGRATION.md). For a whole portal, unshare or delete the sink item; widgets stop on their next page load.

**How do I delete old rows?**
Run a delete against the table with a publisher account, for example with the ArcGIS API for Python: `table.delete_features(where="occurred_at < CURRENT_TIMESTAMP - INTERVAL '365' DAY")`. The table's capabilities are Create only, so temporarily add Delete, run it, and set it back (the `verify` mode of the setup script does exactly that for its test row).

**The setup script says `count_distinct` or a chart is spinning.**
See the "About the JSON" section in DASHBOARD.md. Run `--dump` after saving once in the Dashboards editor and compare.

**Can I see this running somewhere?**
The author uses it across a family of public widgets published on GitHub and Esri Community; the dashboard screenshots in the Community post are from that deployment.
