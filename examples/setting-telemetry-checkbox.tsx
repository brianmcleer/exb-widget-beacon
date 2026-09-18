// Example: exposing the off switch in a widget's settings panel (setting.tsx).
// The beacon honors config.telemetry === false; everything else is your existing settings code.
import { React } from 'jimu-core'
import { Checkbox, Label } from 'jimu-ui'
import { SettingRow, SettingSection } from 'jimu-ui/advanced/setting-components'

export function TelemetryRow (props: { config: any; onConfigChange: (c: any) => void }) {
  const on = props.config?.telemetry !== false
  return (
    <SettingSection title="Usage telemetry">
      <SettingRow>
        <Label check className="d-flex align-items-center">
          <Checkbox checked={on} onChange={(e) => props.onConfigChange(props.config.set('telemetry', e.target.checked))} />
          <span className="ml-2">Send anonymous usage and error counts to this portal's beacon table</span>
        </Label>
      </SettingRow>
    </SettingSection>
  )
}
