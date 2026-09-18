// Example: a function component widget wired to the beacon. Only the marked lines are telemetry.
import { React, type AllWidgetProps } from 'jimu-core'
import { Button, TextInput } from 'jimu-ui'
import { beacon } from '../shared/beacon'                            // telemetry

interface Config { telemetry?: boolean }

export default function Widget (props: AllWidgetProps<Config>) {
  const b = React.useMemo(() => beacon.init(props), [props.id])       // telemetry: once per mount
  const [term, setTerm] = React.useState('')
  const [count, setCount] = React.useState<number | null>(null)

  const search = async (): Promise<void> => {
    try {
      const results = await runSearch(term)                           // your real work
      setCount(results.length)
      b.action('search', results.length > 0 ? 'hit' : 'miss')         // telemetry: category, never the search term
    } catch (err) {
      b.error(err, 'search')                                          // telemetry
      setCount(null)
    }
  }

  return (
    <div className="p-2">
      <TextInput value={term} onChange={(e) => setTerm(e.target.value)} />
      <Button onClick={search}>Search</Button>
      {count !== null && <div>{count} results</div>}
    </div>
  )
}

async function runSearch (term: string): Promise<unknown[]> { return [] }
