/** @jsx jsx */
// Example: a class component widget wired to the beacon. Only the marked lines are telemetry.
import { React, jsx, type AllWidgetProps } from 'jimu-core'
import { Button } from 'jimu-ui'
import { beacon, type BeaconHandle } from '../shared/beacon'          // telemetry

interface Config { telemetry?: boolean; layout?: string }
interface State { busy: boolean; message: string }

export default class Widget extends React.PureComponent<AllWidgetProps<Config>, State> {
  state: State = { busy: false, message: '' }
  private b: BeaconHandle = beacon.init(this.props)                    // telemetry: one "open" row per mount

  exportPdf = async (): Promise<void> => {
    this.setState({ busy: true })
    try {
      await this.doExport()                                            // your real work
      this.b.action('export-pdf', this.props.config?.layout ?? 'default')   // telemetry: a counted outcome
      this.setState({ message: 'Done' })
    } catch (err) {
      this.b.error(err, 'export-pdf')                                  // telemetry: a caught error with context
      this.setState({ message: 'Export failed' })
    } finally {
      this.setState({ busy: false })
    }
  }

  private async doExport (): Promise<void> { /* ... */ }

  render () {
    return (
      <div className="p-2">
        <Button onClick={this.exportPdf} disabled={this.state.busy}>Export PDF</Button>
        <div>{this.state.message}</div>
      </div>
    )
  }
}
