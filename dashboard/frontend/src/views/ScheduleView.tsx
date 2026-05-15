import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '../api/client'
import type { Profile, ScheduleEntryStatus, ScheduleEntryRequest } from '../api/client'

const INTERVAL_PRESETS = [6, 12, 24, 48, 72]

function formatCountdown(isoTarget: string | null): string {
  if (!isoTarget) return '—'
  const diff = new Date(isoTarget).getTime() - Date.now()
  if (diff <= 0) return 'overdue'
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor((diff % 3_600_000) / 60_000)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null
  const styles: Record<string, string> = {
    complete:  'bg-green-50 text-green-700 border-green-200',
    failed:    'bg-red-50 text-red-700 border-red-200',
    cancelled: 'bg-gray-50 text-gray-600 border-gray-200',
    error:     'bg-red-50 text-red-700 border-red-200',
  }
  return (
    <span className={`text-xs border rounded px-2 py-0.5 ${styles[status] ?? 'bg-gray-50 text-gray-600 border-gray-200'}`}>
      {status}
    </span>
  )
}

// ── Schedule form (slide-over panel) ──────────────────────────────────────────

interface ScheduleFormProps {
  initial: ScheduleEntryRequest | null  // null = new
  profiles: Profile[]
  onSave: (req: ScheduleEntryRequest) => Promise<void>
  onClose: () => void
}

const EMPTY_DRAFT: ScheduleEntryRequest = {
  label: '',
  enabled: true,
  interval_hours: 24,
  schedule_time: '',
  profile_ids: [],
}

function ScheduleForm({ initial, profiles, onSave, onClose }: ScheduleFormProps) {
  const [form, setForm]         = useState<ScheduleEntryRequest>(initial ?? EMPTY_DRAFT)
  const [customHours, setCustom] = useState<string>('')
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const set = <K extends keyof ScheduleEntryRequest>(k: K, v: ScheduleEntryRequest[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  const isPreset   = INTERVAL_PRESETS.includes(form.interval_hours)
  const allProfiles = form.profile_ids.length === 0

  const toggleProfile = (id: string) => {
    const next = form.profile_ids.includes(id)
      ? form.profile_ids.filter(p => p !== id)
      : [...form.profile_ids, id]
    set('profile_ids', next)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.label.trim()) { setError('Label is required'); return }
    setSaving(true)
    setError(null)
    try {
      await onSave(form)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const isNew = initial === null

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-md bg-white h-full overflow-y-auto shadow-xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isNew ? 'New Schedule' : `Edit: ${initial?.label}`}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</div>
          )}

          {/* Label */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Label</label>
            <input
              className="block w-full rounded-md border-gray-300 border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.label}
              required
              placeholder="e.g. Daily SUV Search"
              onChange={e => set('label', e.target.value)}
            />
          </div>

          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-gray-800">Enabled</div>
              <div className="text-xs text-gray-400 mt-0.5">Runs automatically while the backend is running</div>
            </div>
            <button
              type="button"
              onClick={() => set('enabled', !form.enabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                form.enabled ? 'bg-brand-600' : 'bg-gray-200'
              }`}
            >
              <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                form.enabled ? 'translate-x-6' : 'translate-x-1'
              }`} />
            </button>
          </div>

          {/* Interval */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">Run every</label>
            <div className="flex flex-wrap gap-2 items-center">
              {INTERVAL_PRESETS.map(h => (
                <button
                  key={h}
                  type="button"
                  onClick={() => { set('interval_hours', h); setCustom('') }}
                  className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    form.interval_hours === h && isPreset
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
                  }`}
                >
                  {h}h
                </button>
              ))}
              <input
                type="number"
                min={1}
                max={8760}
                placeholder="Custom"
                value={customHours}
                onChange={e => {
                  setCustom(e.target.value)
                  const n = parseInt(e.target.value, 10)
                  if (!isNaN(n) && n >= 1) set('interval_hours', n)
                }}
                className={`w-24 rounded-md border px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                  !isPreset ? 'border-brand-400 ring-1 ring-brand-300' : 'border-gray-300'
                }`}
              />
              {!isPreset && customHours === '' && (
                <span className="text-xs text-brand-600">{form.interval_hours}h (custom)</span>
              )}
            </div>
          </div>

          {/* Schedule time */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Run at (optional)</label>
            <p className="text-xs text-gray-400 mb-2">
              Run at a specific time of day. Leave empty to run on interval alone.
            </p>
            <div className="flex items-center gap-2">
              <input
                type="time"
                value={form.schedule_time}
                onChange={e => set('schedule_time', e.target.value)}
                className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {form.schedule_time && (
                <button
                  type="button"
                  onClick={() => set('schedule_time', '')}
                  className="text-xs text-gray-400 hover:text-gray-600 underline"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Profiles */}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">Profiles to run</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={allProfiles}
                  onChange={() => set('profile_ids', [])}
                />
                <span className="font-medium">All profiles</span>
              </label>
              {profiles.map(p => (
                <label key={p.profile_id} className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer ml-4">
                  <input
                    type="checkbox"
                    checked={!allProfiles && form.profile_ids.includes(p.profile_id)}
                    onChange={() => toggleProfile(p.profile_id)}
                  />
                  <span>{p.label}</span>
                  <span className="text-xs text-gray-400">
                    {p.vehicles.map(v => v.join(' ')).join(' · ')}
                  </span>
                </label>
              ))}
              {profiles.length === 0 && (
                <p className="text-xs text-gray-400 ml-4">No profiles found.</p>
              )}
            </div>
          </div>

          <div className="pt-2 pb-6 flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-brand-600 text-white rounded-md py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : isNew ? 'Create schedule' : 'Save changes'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Schedule card ──────────────────────────────────────────────────────────────

interface ScheduleCardProps {
  entry: ScheduleEntryStatus
  profiles: Profile[]
  onEdit: () => void
  onDelete: () => void
  onToggleEnabled: () => void
  onRunNow: () => void
  runningJobId: string | null
  tick: number
}

function ScheduleCard({
  entry, profiles, onEdit, onDelete, onToggleEnabled, onRunNow, runningJobId, tick,
}: ScheduleCardProps) {
  const isRunning = !!(entry.running_job || runningJobId)
  const profileLabels = entry.profile_ids.length === 0
    ? 'All profiles'
    : entry.profile_ids
        .map(id => profiles.find(p => p.profile_id === id)?.label ?? id)
        .join(', ')

  return (
    <div className={`bg-white border rounded-lg p-4 transition-colors ${
      entry.enabled ? 'border-gray-200 hover:border-gray-300' : 'border-gray-100 opacity-70'
    }`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={onToggleEnabled}
            title={entry.enabled ? 'Disable' : 'Enable'}
            className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors ${
              entry.enabled ? 'bg-brand-600' : 'bg-gray-200'
            }`}
          >
            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
              entry.enabled ? 'translate-x-4' : 'translate-x-0.5'
            }`} />
          </button>
          <h3 className="font-semibold text-gray-900 truncate">{entry.label}</h3>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            onClick={onRunNow}
            disabled={isRunning}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isRunning
              ? <><span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" /> Running…</>
              : '▶ Run Now'}
          </button>
          <button
            onClick={onEdit}
            className="px-2.5 py-1 text-xs border border-gray-200 rounded hover:bg-gray-50 text-gray-600"
          >
            Edit
          </button>
          <button
            onClick={onDelete}
            className="px-2.5 py-1 text-xs border border-red-200 rounded hover:bg-red-50 text-red-600"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Meta row */}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
        <span>Every {entry.interval_hours}h{entry.schedule_time ? ` at ${entry.schedule_time}` : ''}</span>
        <span className="text-gray-300">·</span>
        <span>{profileLabels}</span>
      </div>

      {/* Status rows */}
      <div className="mt-3 space-y-1 text-xs text-gray-500 border-t border-gray-100 pt-2">
        {entry.enabled && (
          <div className="flex justify-between">
            <span>Next run</span>
            <span className="font-medium text-gray-700" key={tick}>
              {formatCountdown(entry.next_run_at)}
              {entry.next_run_at && (
                <span className="text-gray-400 ml-1.5">({formatTime(entry.next_run_at)})</span>
              )}
            </span>
          </div>
        )}
        {entry.last_run_at && (
          <div className="flex justify-between items-center">
            <span>Last run</span>
            <span className="flex items-center gap-1.5">
              {formatTime(entry.last_run_at)}
              <StatusBadge status={entry.last_status} />
            </span>
          </div>
        )}
        {!entry.last_run_at && !entry.enabled && (
          <span className="text-gray-400 italic">Disabled</span>
        )}
        {!entry.last_run_at && entry.enabled && (
          <span className="text-gray-400 italic">Never run</span>
        )}
      </div>
    </div>
  )
}

// ── Main view ─────────────────────────────────────────────────────────────────

export function ScheduleView() {
  const [schedules, setSchedules] = useState<ScheduleEntryStatus[]>([])
  const [profiles, setProfiles]   = useState<Profile[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [editing, setEditing]     = useState<ScheduleEntryStatus | null | undefined>(undefined) // undefined = closed, null = new
  const [deleting, setDeleting]   = useState<string | null>(null)
  const [runningNow, setRunningNow] = useState<Record<string, string>>({}) // scheduleId → jobId
  const [tick, setTick]           = useState(0)
  const pollRef                   = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(() => {
    api.schedules.list()
      .then(res => {
        setSchedules(res.schedules)
        setLoading(false)
        // Clear runningNow entries whose jobs are no longer active
        setRunningNow(prev => {
          const next = { ...prev }
          let changed = false
          for (const [scheduleId, jobId] of Object.entries(prev)) {
            const entry = res.schedules.find(s => s.id === scheduleId)
            if (!entry || (entry.running_job?.job_id !== jobId && !entry.running_job)) {
              delete next[scheduleId]
              changed = true
            }
          }
          return changed ? next : prev
        })
      })
      .catch(e => { setError(e instanceof Error ? e.message : 'Failed to load schedules'); setLoading(false) })
  }, [])

  useEffect(() => {
    api.profiles.list().then(setProfiles).catch(console.error)
    load()
  }, [load])

  // Poll every 15s (faster when a run-now is active)
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    const hasActiveRun = Object.keys(runningNow).length > 0
    pollRef.current = setInterval(load, hasActiveRun ? 5_000 : 15_000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [load, runningNow])

  // Countdown tick every 30s
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 30_000)
    return () => clearInterval(id)
  }, [])

  const handleRunNow = async (scheduleId: string) => {
    try {
      const { job_id } = await api.schedules.runNow(scheduleId)
      setRunningNow(prev => ({ ...prev, [scheduleId]: job_id }))
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Run failed')
    }
  }

  const handleToggleEnabled = async (entry: ScheduleEntryStatus) => {
    try {
      const updated = await api.schedules.update(entry.id, {
        label:          entry.label,
        enabled:        !entry.enabled,
        interval_hours: entry.interval_hours,
        schedule_time:  entry.schedule_time,
        profile_ids:    entry.profile_ids,
      })
      setSchedules(prev => prev.map(s => s.id === entry.id ? updated : s))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Update failed')
    }
  }

  const handleSave = async (req: ScheduleEntryRequest) => {
    if (editing === null) {
      const created = await api.schedules.create(req)
      setSchedules(prev => [...prev, created])
    } else if (editing) {
      const updated = await api.schedules.update(editing.id, req)
      setSchedules(prev => prev.map(s => s.id === editing.id ? updated : s))
    }
    setEditing(undefined)
  }

  const confirmDelete = async () => {
    if (!deleting) return
    try {
      await api.schedules.delete(deleting)
      setSchedules(prev => prev.filter(s => s.id !== deleting))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  if (loading) return <div className="text-sm text-gray-400 text-center py-16">Loading…</div>

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Schedules</h1>
          <p className="text-xs text-gray-400 mt-0.5">Runs automatically while the app is open in the system tray.</p>
        </div>
        <button
          onClick={() => setEditing(null)}
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700"
        >
          + New Schedule
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-bold">×</button>
        </div>
      )}

      <div className="space-y-3">
        {schedules.map(entry => (
          <ScheduleCard
            key={entry.id}
            entry={entry}
            profiles={profiles}
            tick={tick}
            runningJobId={runningNow[entry.id] ?? null}
            onEdit={() => setEditing(entry)}
            onDelete={() => setDeleting(entry.id)}
            onToggleEnabled={() => handleToggleEnabled(entry)}
            onRunNow={() => handleRunNow(entry.id)}
          />
        ))}

        {schedules.length === 0 && (
          <div className="text-center py-16 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
            No schedules yet — click "+ New Schedule" to create one.
          </div>
        )}
      </div>

      {/* Edit / create slide-over */}
      {editing !== undefined && (
        <ScheduleForm
          initial={editing === null ? null : {
            label:          editing.label,
            enabled:        editing.enabled,
            interval_hours: editing.interval_hours,
            schedule_time:  editing.schedule_time,
            profile_ids:    editing.profile_ids,
          }}
          profiles={profiles}
          onSave={handleSave}
          onClose={() => setEditing(undefined)}
        />
      )}

      {/* Delete confirmation */}
      {deleting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete schedule?</h3>
            <p className="text-sm text-gray-600 mb-4">
              This schedule and its configuration will be removed. Active runs will continue to completion.
            </p>
            <div className="flex gap-3">
              <button onClick={confirmDelete}
                className="flex-1 bg-red-600 text-white rounded-md py-2 text-sm font-medium hover:bg-red-700">
                Delete
              </button>
              <button onClick={() => setDeleting(null)}
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
