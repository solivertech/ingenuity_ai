import { useEffect, useState } from 'react'
import { api, BUILTIN_DOMAINS } from '../api/client'
import type { DocFile, DomainConfig, BuiltinDomain } from '../api/client'

const _BUILTIN_DOMAIN_TYPES: Record<string, string> = Object.fromEntries(
  BUILTIN_DOMAINS.map(d => [d.domain_id, d.domain_type])
)

function toSlug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

function GenerateModal({ onClose, onSaved }: { onClose: () => void; onSaved: (filename: string, content: string) => void }) {
  const [topic, setTopic]           = useState('')
  const [description, setDesc]      = useState('')
  const [domainId, setDomainId]     = useState<string>('')  // '' = none
  const [make, setMake]             = useState('')
  const [model, setModel]           = useState('')
  const [yearStart, setYearStart]   = useState(2021)
  const [yearEnd, setYearEnd]       = useState(2025)
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated]   = useState<string | null>(null)
  const [filename, setFilename]     = useState('')
  const [saving, setSaving]         = useState(false)
  const [err, setErr]               = useState<string | null>(null)
  const [allDomains, setAllDomains] = useState<BuiltinDomain[]>([...BUILTIN_DOMAINS])

  const inputCls = 'block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500'

  useEffect(() => {
    api.domains.list().then(res => {
      const saved = res.domains.map((d: DomainConfig) => ({
        domain_id: d.domain_id,
        display_name: d.display_name,
        domain_type: d.domain_type ?? 'generic',
      }))
      setAllDomains([...BUILTIN_DOMAINS, ...saved])
    }).catch(() => {})
  }, [])

  const isAutomotive = (_BUILTIN_DOMAIN_TYPES[domainId] ?? allDomains.find(d => d.domain_id === domainId)?.domain_type ?? 'generic') === 'automotive'

  // Auto-fill topic from make+model when automotive fields change
  const handleMakeModel = (newMake: string, newModel: string) => {
    if (newMake || newModel) {
      const composed = [newMake, newModel].filter(Boolean).join(' ')
      setTopic(composed)
    }
  }

  const generate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim()) return
    setErr(null); setGenerating(true)
    try {
      const extra: Record<string, unknown> = {}
      if (isAutomotive) {
        if (make)  extra.make       = make
        if (model) extra.model      = model
        extra.year_start = yearStart
        extra.year_end   = yearEnd
      }
      const res = await api.docs.generate({
        topic: topic.trim(),
        description,
        domain_id: domainId || undefined,
        extra: Object.keys(extra).length ? extra : undefined,
      })
      setGenerated(res.content)
      setFilename(`${toSlug(topic) || 'reference'}.md`)
    } catch (e) { setErr(e instanceof Error ? e.message : 'Generation failed') }
    finally { setGenerating(false) }
  }

  const save = async () => {
    if (!generated || !filename) return
    setSaving(true); setErr(null)
    try {
      await api.docs.put(filename, generated)
      onSaved(filename, generated)
    } catch (e) { setErr(e instanceof Error ? e.message : 'Save failed') }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 flex flex-col max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-semibold text-gray-900">Generate Reference Doc</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {err && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{err}</div>
          )}

          {!generated ? (
            <form onSubmit={generate} className="space-y-5">
              <p className="text-sm text-gray-500">
                AI generates a structured reference guide that helps evaluate and compare listings.
              </p>

              {/* Domain (optional) */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Domain <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <select
                  className={inputCls}
                  value={domainId}
                  onChange={e => { setDomainId(e.target.value); setMake(''); setModel('') }}
                >
                  <option value="">None — generic reference doc</option>
                  {allDomains.map(d => (
                    <option key={d.domain_id} value={d.domain_id}>{d.display_name}</option>
                  ))}
                </select>
              </div>

              {/* Automotive extras */}
              {isAutomotive && (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Automotive details</p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Make <span className="text-gray-400 font-normal">(optional)</span>
                      </label>
                      <input
                        className={inputCls}
                        placeholder="Honda"
                        value={make}
                        onChange={e => { setMake(e.target.value); handleMakeModel(e.target.value, model) }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Model <span className="text-gray-400 font-normal">(optional)</span>
                      </label>
                      <input
                        className={inputCls}
                        placeholder="CR-V"
                        value={model}
                        onChange={e => { setModel(e.target.value); handleMakeModel(make, e.target.value) }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Year start</label>
                      <input type="number" className={inputCls} value={yearStart}
                        onChange={e => setYearStart(Number(e.target.value))} />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Year end</label>
                      <input type="number" className={inputCls} value={yearEnd}
                        onChange={e => setYearEnd(Number(e.target.value))} />
                    </div>
                  </div>
                </div>
              )}

              {/* Topic */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject / topic</label>
                <input
                  className={inputCls}
                  required
                  placeholder="e.g. Honda CR-V, Standing desk, 2BR apartment in Austin"
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  What I'm looking for <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <textarea
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  rows={3}
                  placeholder="Describe your priorities, budget, location, must-haves, or anything else that should inform the guide…"
                  value={description}
                  onChange={e => setDesc(e.target.value)}
                />
              </div>

              <button type="submit" disabled={generating || !topic.trim()}
                className="w-full bg-brand-600 text-white rounded-md py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
                {generating ? 'Generating…' : 'Generate reference doc'}
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Save as filename</label>
                  <input className={inputCls} value={filename} onChange={e => setFilename(e.target.value)}
                    pattern="[\w\-]+\.md" title="e.g. honda_crv.md" />
                </div>
                <button onClick={() => setGenerated(null)} className="mt-5 text-sm text-brand-600 hover:underline shrink-0">
                  Regenerate
                </button>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Generated content (editable)</label>
                <textarea
                  className="w-full font-mono text-xs border border-gray-200 rounded p-3 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  rows={18}
                  value={generated}
                  onChange={e => setGenerated(e.target.value)}
                />
              </div>
              <div className="flex gap-3">
                <button onClick={save} disabled={saving || !filename}
                  className="flex-1 bg-brand-600 text-white rounded-md py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
                  {saving ? 'Saving…' : 'Save doc'}
                </button>
                <button onClick={onClose}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">
                  Discard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function DocsView() {
  const [docs, setDocs]           = useState<DocFile[]>([])
  const [selected, setSelected]   = useState<string | null>(null)
  const [content, setContent]     = useState('')
  const [draft, setDraft]         = useState('')
  const [newName, setNewName]     = useState('')
  const [creating, setCreating]   = useState(false)
  const [saving, setSaving]       = useState(false)
  const [deleting, setDeleting]   = useState<string | null>(null)
  const [error, setError]         = useState<string | null>(null)
  const [saved, setSaved]         = useState(false)
  const [showGenerate, setShowGenerate] = useState(false)

  const load = () => { api.docs.list().then(setDocs).catch(console.error) }
  useEffect(load, [])

  const openDoc = async (filename: string) => {
    setError(null)
    setSaved(false)
    try {
      const { content: c } = await api.docs.get(filename)
      setSelected(filename)
      setContent(c)
      setDraft(c)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load doc')
    }
  }

  const saveDoc = async () => {
    const filename = creating ? newName : selected
    if (!filename) return
    setSaving(true)
    setError(null)
    try {
      await api.docs.put(filename, draft)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      if (creating) {
        setCreating(false)
        setNewName('')
        setSelected(filename)
        setContent(draft)
      } else {
        setContent(draft)
      }
      load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    try {
      await api.docs.delete(deleting)
      if (selected === deleting) { setSelected(null); setContent(''); setDraft('') }
      setDeleting(null)
      load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed')
      setDeleting(null)
    }
  }

  const startNew = () => {
    setCreating(true)
    setSelected(null)
    setNewName('')
    setDraft('')
    setContent('')
  }

  const isDirty = draft !== content

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Reference Docs</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            AI-generated guides fed to the LLM when evaluating listings.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowGenerate(true)}
            className="px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-md hover:bg-violet-700">
            Generate with AI
          </button>
          <button onClick={startNew}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700">
            + New doc
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3 flex justify-between">
          {error} <button onClick={() => setError(null)} className="font-bold ml-2">×</button>
        </div>
      )}

      <div className="flex gap-4 h-[calc(100vh-220px)]">
        {/* File list */}
        <div className="w-64 flex-shrink-0 bg-white border border-gray-200 rounded-lg overflow-y-auto">
          {docs.map(d => (
            <div key={d.filename}
              className={`flex items-start justify-between px-3 py-2.5 cursor-pointer border-b border-gray-100 hover:bg-gray-50 ${selected === d.filename ? 'bg-brand-50' : ''}`}
              onClick={() => openDoc(d.filename)}
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-800 truncate">{d.filename}</div>
                <div className="text-xs text-gray-400">{(d.size_bytes / 1024).toFixed(1)} KB</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {d.matched_profiles.map(p => (
                    <span key={p} className="text-xs bg-brand-100 text-brand-700 rounded px-1.5">{p}</span>
                  ))}
                </div>
              </div>
              <button onClick={e => { e.stopPropagation(); setDeleting(d.filename) }}
                className="text-gray-300 hover:text-red-500 ml-2 mt-0.5 text-sm flex-shrink-0">✕</button>
            </div>
          ))}
          {docs.length === 0 && (
            <div className="text-center py-8 text-sm text-gray-400">No docs yet</div>
          )}
        </div>

        {/* Editor */}
        <div className="flex-1 flex flex-col bg-white border border-gray-200 rounded-lg overflow-hidden">
          {(selected || creating) ? (
            <>
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 bg-gray-50">
                {creating ? (
                  <input
                    className="text-sm border border-gray-300 rounded px-2 py-1 w-48 focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="filename.md"
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    autoFocus
                  />
                ) : (
                  <span className="text-sm font-medium text-gray-700">{selected}</span>
                )}
                <div className="flex items-center gap-2">
                  {saved && <span className="text-xs text-emerald-600">✓ Saved</span>}
                  {isDirty && !saved && <span className="text-xs text-amber-500">Unsaved changes</span>}
                  <button onClick={saveDoc} disabled={saving || (!creating && !isDirty) || (creating && !newName)}
                    className="px-3 py-1 bg-brand-600 text-white text-sm rounded hover:bg-brand-700 disabled:opacity-40">
                    {saving ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </div>
              <textarea
                className="flex-1 p-4 font-mono text-sm resize-none focus:outline-none"
                value={draft}
                onChange={e => setDraft(e.target.value)}
                placeholder="# Reference doc content…"
                spellCheck={false}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              Select a doc to edit, or create a new one
            </div>
          )}
        </div>
      </div>

      {deleting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete doc?</h3>
            <p className="text-sm text-gray-600 mb-4">
              Delete <code className="text-xs bg-gray-100 px-1 rounded">{deleting}</code>? Profiles that reference it directly will need to be updated.
            </p>
            <div className="flex gap-3">
              <button onClick={confirmDelete}
                className="flex-1 bg-red-600 text-white rounded-md py-2 text-sm font-medium hover:bg-red-700">Delete</button>
              <button onClick={() => setDeleting(null)}
                className="flex-1 border border-gray-300 rounded-md py-2 text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {showGenerate && (
        <GenerateModal
          onClose={() => setShowGenerate(false)}
          onSaved={(filename, generatedContent) => {
            setShowGenerate(false)
            setCreating(false)
            setSelected(filename)
            setContent(generatedContent)
            setDraft(generatedContent)
            load()
          }}
        />
      )}
    </div>
  )
}
