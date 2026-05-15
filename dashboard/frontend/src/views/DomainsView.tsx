import { useEffect, useRef, useState } from 'react'
import { api, API_BASE } from '../api/client'
import type { DomainConfig, FieldSchema } from '../api/client'

interface DiscoverSSEEvent {
  type:     'log' | 'result' | 'error'
  message?: string
  config?:  DomainConfig
}

// ── Domain list ───────────────────────────────────────────────────────────────

export function DomainsView() {
  const [domains, setDomains]       = useState<DomainConfig[]>([])
  const [showWizard, setShowWizard] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [error, setError]           = useState<string | null>(null)
  const [loading, setLoading]       = useState(true)

  const load = () => {
    setLoading(true)
    api.domains.list()
      .then(r => setDomains(r.domains))
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load domains'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const confirmDelete = async () => {
    if (!deletingId) return
    try {
      await api.domains.delete(deletingId)
      setDeletingId(null)
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed')
      setDeletingId(null)
    }
  }

  if (showWizard) {
    return <DomainWizard onClose={() => { setShowWizard(false); load() }} />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Domains</h1>
          <p className="text-sm text-gray-500 mt-0.5">AI-discovered scraping configurations</p>
        </div>
        <button
          onClick={() => setShowWizard(true)}
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700"
        >
          + Discover new domain
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-bold">×</button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading…</div>
      ) : domains.length === 0 ? (
        <div className="text-center py-16 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg space-y-2">
          <div className="text-3xl">🔍</div>
          <p>No domains discovered yet.</p>
          <p className="text-sm">Click "Discover new domain" to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {domains.map(d => (
            <div key={d.domain_id} className="bg-white border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{d.display_name}</h3>
                  <code className="text-xs text-gray-400">{d.domain_id}</code>
                </div>
                <button
                  onClick={() => setDeletingId(d.domain_id)}
                  className="text-xs px-2.5 py-1 border border-red-200 rounded hover:bg-red-50 text-red-600"
                >
                  Delete
                </button>
              </div>

              <div className="mt-3 space-y-1 text-sm text-gray-600">
                <div className="truncate text-xs text-gray-400">{d.base_url}</div>
                <div className="flex gap-4 text-xs">
                  <span><span className="font-medium text-gray-700">Fields: </span>{d.fields.length}</span>
                  <span><span className="font-medium text-gray-700">Pages: </span>{d.max_pages}</span>
                  <span><span className="font-medium text-gray-700">Pagination: </span>{d.pagination_style}</span>
                </div>
                {d.created_at && (
                  <div className="text-xs text-gray-400">
                    Discovered {new Date(d.created_at).toLocaleDateString()}
                  </div>
                )}
              </div>

              <div className="mt-3 flex flex-wrap gap-1">
                {d.fields.slice(0, 6).map(f => (
                  <span key={f.name} className="text-xs px-2 py-0.5 bg-brand-50 text-brand-700 rounded-full">
                    {f.display_name}
                  </span>
                ))}
                {d.fields.length > 6 && (
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">
                    +{d.fields.length - 6} more
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {deletingId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete domain?</h3>
            <p className="text-sm text-gray-600 mb-4">
              This removes <code className="text-xs bg-gray-100 px-1 rounded">{deletingId}</code> from
              saved configs. Existing run history is not affected.
            </p>
            <div className="flex gap-3">
              <button onClick={confirmDelete}
                className="flex-1 bg-red-600 text-white rounded-md py-2 text-sm font-medium hover:bg-red-700">
                Delete
              </button>
              <button onClick={() => setDeletingId(null)}
                className="flex-1 border border-gray-300 rounded-md py-2 text-sm text-gray-600 hover:bg-gray-50">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Wizard ────────────────────────────────────────────────────────────────────

const STEPS = ['URL & request', 'Discovery', 'Schema preview', 'Edit fields', 'Confirm']

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center">
      {STEPS.map((label, i) => {
        const n = i + 1
        const done   = current > n
        const active = current === n
        return (
          <div key={n} className="flex items-center flex-1 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <div className={`w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${
                done   ? 'bg-brand-600 text-white' :
                active ? 'bg-brand-100 text-brand-700 ring-2 ring-brand-500' :
                         'bg-gray-100 text-gray-400'
              }`}>
                {done ? '✓' : n}
              </div>
              <span className={`text-xs truncate hidden sm:block ${
                active ? 'text-brand-700 font-medium' : 'text-gray-400'
              }`}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`h-px flex-1 mx-2 ${done ? 'bg-brand-300' : 'bg-gray-200'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function DomainWizard({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(1)

  // Step 1
  const [url, setUrl]               = useState('')
  const [userRequest, setUserRequest] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [domainId, setDomainId]     = useState('')
  const [idTouched, setIdTouched]   = useState(false)

  // Step 2
  const [logs, setLogs]                     = useState<string[]>([])
  const [discovering, setDiscovering]       = useState(false)
  const [discoveryError, setDiscoveryError] = useState<string | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  // Steps 3 & 4
  const [config, setConfig]               = useState<DomainConfig | null>(null)
  const [editedFields, setEditedFields]   = useState<FieldSchema[]>([])

  // Step 5
  const [saving, setSaving]       = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const autoSlug = (v: string) =>
    v.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')

  const handleDisplayNameChange = (v: string) => {
    setDisplayName(v)
    if (!idTouched) setDomainId(autoSlug(v))
  }

  const startDiscovery = async () => {
    setStep(2)
    setDiscovering(true)
    setLogs([])
    setDiscoveryError(null)
    try {
      const resp = await fetch(`${API_BASE}/domains/discover`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          url,
          user_request: userRequest,
          domain_id:    domainId,
          display_name: displayName,
        }),
      })
      if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`)

      const reader  = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer    = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE events are delimited by '\n\n'
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const dataLine = part.split('\n').find(l => l.startsWith('data: '))
          if (!dataLine) continue
          try {
            const evt = JSON.parse(dataLine.slice(6)) as DiscoverSSEEvent
            if (evt.type === 'log') {
              setLogs(prev => [...prev, evt.message ?? ''])
            } else if (evt.type === 'result' && evt.config) {
              setConfig(evt.config)
              setEditedFields(evt.config.fields)
              setDiscovering(false)
              setStep(3)
            } else if (evt.type === 'error') {
              setDiscoveryError(evt.message ?? 'Discovery failed')
              setDiscovering(false)
            }
          } catch { /* malformed SSE line — skip */ }
        }
      }
    } catch (err) {
      setDiscoveryError(err instanceof Error ? err.message : 'Discovery failed')
    } finally {
      setDiscovering(false)
    }
  }

  const updateField = (idx: number, key: keyof FieldSchema, value: unknown) => {
    setEditedFields(prev => prev.map((f, i) => i === idx ? { ...f, [key]: value } : f))
  }

  const handleSave = async (_fromStep: number) => {
    if (!config) return
    setSaving(true)
    setSaveError(null)
    try {
      const changed = JSON.stringify(editedFields) !== JSON.stringify(config.fields)
      if (changed) await api.domains.update(domainId, { fields: editedFields })
      setStep(5)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const step1Valid = url.trim() && userRequest.trim() && displayName.trim() &&
    /^[a-z0-9_]+$/.test(domainId)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Discover new domain</h1>
        <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">
          ← Back to domains
        </button>
      </div>

      <StepIndicator current={step} />

      {/* ── Step 1: URL & request ── */}
      {step === 1 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">Display name</label>
              <input
                type="text"
                value={displayName}
                onChange={e => handleDisplayNameChange(e.target.value)}
                placeholder="Zillow Austin Homes"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">
                Domain ID <span className="text-gray-400 font-normal">(slug)</span>
              </label>
              <input
                type="text"
                value={domainId}
                onChange={e => { setDomainId(e.target.value); setIdTouched(true) }}
                placeholder="zillow_austin_homes"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {domainId && !/^[a-z0-9_]+$/.test(domainId) && (
                <p className="text-xs text-red-500">Only lowercase letters, numbers, underscores</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Target URL</label>
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://www.example.com/listings"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">
              What data do you want to extract?
            </label>
            <p className="text-xs text-gray-500">
              Describe the fields you need. The more specific, the better the results.
            </p>
            <textarea
              value={userRequest}
              onChange={e => setUserRequest(e.target.value)}
              rows={5}
              placeholder={"I want to track listings. Extract these fields:\n- Price\n- Square footage\n- Bedrooms / bathrooms\n- Address\n- Days on market\n- Listing URL"}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>

          <div className="flex justify-end">
            <button
              onClick={startDiscovery}
              disabled={!step1Valid}
              className="px-5 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Start discovery →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Discovery log stream ── */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="rounded-lg overflow-hidden border border-gray-700 bg-gray-900 font-mono text-sm">
            <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 border-b border-gray-700">
              <span className="text-gray-400 text-xs">Schema discovery</span>
              {discovering && (
                <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Running
                </span>
              )}
              {!discovering && !discoveryError && (
                <span className="text-xs font-semibold text-emerald-400">✓ Complete</span>
              )}
              {discoveryError && (
                <span className="text-xs font-semibold text-red-400">✗ Failed</span>
              )}
            </div>
            <div className="h-72 overflow-y-auto p-3 space-y-0.5">
              {logs.length === 0 && discovering && (
                <span className="text-gray-500 italic">Launching browser…</span>
              )}
              {logs.map((msg, i) => (
                <div key={i} className="leading-5 text-gray-200">{msg}</div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>

          {discoveryError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
              <p className="text-sm font-medium text-red-700">Discovery failed</p>
              <p className="text-sm text-red-600">{discoveryError}</p>
              <div className="flex gap-3">
                <button
                  onClick={() => { setStep(1); setDiscoveryError(null) }}
                  className="px-4 py-1.5 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
                >
                  ← Edit inputs
                </button>
                <button
                  onClick={startDiscovery}
                  className="px-4 py-1.5 bg-brand-600 text-white rounded-md text-sm font-medium hover:bg-brand-700"
                >
                  Retry
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Step 3: Schema preview ── */}
      {step === 3 && config && (
        <div className="space-y-4">
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 text-sm text-emerald-800">
            ✓ Discovered <strong>{config.fields.length} fields</strong> from{' '}
            <span className="font-mono text-xs">{config.base_url}</span>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-700">Discovered fields</h3>
              <div className="flex gap-3 text-xs text-gray-500">
                <span>Pagination: <strong className="text-gray-700">{config.pagination_style}</strong></span>
                <span>·</span>
                <span>Max pages: <strong className="text-gray-700">{config.max_pages}</strong></span>
              </div>
            </div>
            <table className="min-w-full text-sm divide-y divide-gray-100">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  {['Field name', 'Display name', 'Type', 'Unit', 'Required', 'Primary sort'].map(h => (
                    <th key={h} className="px-4 py-2 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {config.fields.map(f => (
                  <tr key={f.name} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-mono text-xs text-gray-500">{f.name}</td>
                    <td className="px-4 py-2 text-gray-700">{f.display_name}</td>
                    <td className="px-4 py-2 text-gray-500">{f.data_type}</td>
                    <td className="px-4 py-2 text-gray-400">{f.unit || '—'}</td>
                    <td className="px-4 py-2">
                      {f.required
                        ? <span className="text-emerald-600 font-bold">✓</span>
                        : <span className="text-gray-200">—</span>}
                    </td>
                    <td className="px-4 py-2">
                      {f.is_primary_sort
                        ? <span className="text-brand-500">★</span>
                        : <span className="text-gray-200">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setStep(4)}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
            >
              Edit fields →
            </button>
            <button
              onClick={() => handleSave(3)}
              disabled={saving}
              className="px-5 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save as-is →'}
            </button>
          </div>
          {saveError && <p className="text-sm text-red-600">{saveError}</p>}
        </div>
      )}

      {/* ── Step 4: Edit fields ── */}
      {step === 4 && config && (
        <div className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-medium text-gray-700">Edit fields</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Adjust display names, types, and units. Extraction paths are managed automatically.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm divide-y divide-gray-100">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                  <tr>
                    {['Field name', 'Display name', 'Type', 'Unit', 'Required'].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {editedFields.map((f, idx) => (
                    <tr key={f.name}>
                      <td className="px-3 py-2 font-mono text-xs text-gray-400">{f.name}</td>
                      <td className="px-3 py-1.5">
                        <input
                          type="text"
                          value={f.display_name}
                          onChange={e => updateField(idx, 'display_name', e.target.value)}
                          className="w-full border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-400"
                        />
                      </td>
                      <td className="px-3 py-1.5">
                        <select
                          value={f.data_type}
                          onChange={e => updateField(idx, 'data_type', e.target.value)}
                          className="border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-400"
                        >
                          {['float', 'int', 'str', 'bool'].map(t => (
                            <option key={t} value={t}>{t}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1.5">
                        <input
                          type="text"
                          value={f.unit}
                          onChange={e => updateField(idx, 'unit', e.target.value)}
                          placeholder="$, mi, sqft…"
                          className="w-24 border border-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-brand-400"
                        />
                      </td>
                      <td className="px-3 py-1.5 text-center">
                        <input
                          type="checkbox"
                          checked={f.required}
                          onChange={e => updateField(idx, 'required', e.target.checked)}
                          className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setStep(3)}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
            >
              ← Back
            </button>
            <button
              onClick={() => handleSave(4)}
              disabled={saving}
              className="px-5 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save domain →'}
            </button>
          </div>
          {saveError && <p className="text-sm text-red-600">{saveError}</p>}
        </div>
      )}

      {/* ── Step 5: Confirmation ── */}
      {step === 5 && (
        <div className="bg-white border border-gray-200 rounded-lg p-10 text-center space-y-4">
          <div className="text-5xl">✓</div>
          <h2 className="text-lg font-semibold text-gray-900">Domain saved</h2>
          <p className="text-sm text-gray-600 max-w-sm mx-auto">
            <strong>{displayName}</strong>{' '}
            (<code className="text-xs bg-gray-100 px-1 rounded">{domainId}</code>)
            is ready to use. Reference it by domain_id in your profiles.yaml.
          </p>
          <div className="pt-2">
            <button
              onClick={onClose}
              className="px-6 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700"
            >
              View domains
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
