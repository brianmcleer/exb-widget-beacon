# Wiring a widget

## 1. Copy the file

`src/beacon.ts` goes to `your-widget/src/shared/beacon.ts`. It imports only `getAppStore` from `jimu-core`, so no `package.json` change and no new dependency. Do not change your `tsconfig.json`; the file has no JSX.

If you maintain several widgets, keep one master copy somewhere outside the widgets (for example `your-extensions/widgets/_shared/beacon.ts`) and copy it byte for byte into each widget's `src/shared/`. A small sync script beats editing copies by hand.

## 2. Initialize once per widget instance

`beacon.init(props)` reads the manifest name and version and the config from the widget props, records an "open" event, and returns a handle. Call it once when the widget mounts.

Class component:

```tsx
import { React } from 'jimu-core'
import { beacon, type BeaconHandle } from '../shared/beacon'

export default class Widget extends React.PureComponent<AllWidgetProps<IMConfig>, State> {
  private b: BeaconHandle = beacon.init(this.props)   // or in componentDidMount
  ...
}
```

Function component:

```tsx
const b = React.useMemo(() => beacon.init(props), [props.id])
```

The handle never throws and is a no-op when telemetry is off, so there is nothing to guard.

## 3. Record the actions worth counting

Two to six per widget is plenty. Count outcomes people care about, not every click.

```tsx
b.action('export-pdf', `${layoutName} ${orientation}`)
b.action('search', resultCount > 0 ? 'hit' : 'miss')
b.action('help-open')
```

Naming rules that keep the dashboard readable:

- lowercase, hyphenated, stable across versions (`export-pdf`, not `Export PDF (new)`);
- the same name in every widget for the same idea (`help-open`, `search`, `export-*`);
- `detail` is for a short category or mode, not for data. It is truncated at 250 characters and scrubbed, but the rule is simpler than that: never put a user's input, a feature attribute, a coordinate or a URL in it.

Reserved names the module uses itself: `open`, `loaded`, `error`, `unhandled-error`.

## 4. Record caught errors

```tsx
try {
  await exportPdf()
} catch (err) {
  b.error(err, 'export-pdf')
  this.setState({ message: 'Export failed' })   // your own handling stays
}
```

`error_text` gets the message and the first six stack lines, scrubbed of `token=`, query strings and email addresses, cut at 1000 characters. At most 25 errors are sent per page session so a loop cannot flood the table.

Unhandled errors and unhandled promise rejections are captured once per page by the first widget that initializes, and attributed to a widget when its `dist` folder appears in the stack. You do not need to add anything for that.

## 5. Optional: a telemetry switch in your settings panel

The module honors `config.telemetry === false`. Add a checkbox to `setting.tsx` that writes that key and app builders can turn it off per widget instance:

```tsx
<Checkbox checked={config.telemetry !== false}
          onChange={(e) => onSettingChange({ id, config: config.set('telemetry', e.target.checked) })} />
```

## 6. Rebuild and redeploy

Rebuild the widget and republish the apps that use it. An app that was published before the change keeps its old copy of the widget and reports nothing.

## 7. Check it works

Open a published app, press F12, Network tab, filter on `applyEdits`. Within about ten seconds of the widget opening you should see a POST to `.../exb_widget_beacon/FeatureServer/0/applyEdits` returning 200 with `addResults`. If nothing appears: the portal has no item tagged `exb-beacon-sink` (run `setup/beacon_sink_setup.py verify`), the browser has Do Not Track on, or the app is open in the editor.

## What you should not do

- Do not put the sink URL in the widget. The portal lookup is the whole point: your widget stays organization neutral and anyone can install it without sending you their traffic. `beacon.configure(url)` exists for unit tests only.
- Do not record identifying data in `detail`. If you find yourself wanting to, make it a category ("parcel", "address", "coordinates") instead.
- Do not call `init` on every render. Once per mount.
