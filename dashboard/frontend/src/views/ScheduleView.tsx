import { useEffect, useState, useCallback, useRef } from 'react'
import { api } from '../api/client'
import type { Profile, ScheduleStatus, ScheduleRequest } from '../api/client'

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

export function ScheduleView() {
  const [status, setStatus]         = useState<ScheduleStatus | null>(null)
  const [profiles, setProfiles]     = useState<Profile[]>([])
  const [draft, setDraft]           = useState<ScheduleRequest | null>(null)
  const [customHours, setCustom]    = useState<string>('')
  const [saving, setSaving]         = useState(false)
  const [saved, setSaved]           = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [runningNow, setRunningNow] = useState<string | null>(null)  // job_id
  const [runNowError, setRunNowError] = useState<string | null>(null)
  const [tick, setTick]             = useState(0)
  const pollRef                     = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadStatus = useCallback(() => {
    api.schedule.get()
      .then(s => {
        setStatus(s)
        setDraft(prev => prev ?? {
          enabled:        s.enabled,
          interval_hours: s.interval_hours,
          schedule_time:  s.schedule_time ?? '',
          profile_ids:    s.profile_ids,
        })
        // Clear runningNow once the job is no longer active
        if (runningNow && !s.running_job) {
          setRunningNow(null)
        }
      })
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load schedule'))
  }, [runningNow])

  // Restart polling interval — faster while a run-now is in progress
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    const interval = runningNow ? 5_000 : 30_000
    pollRef.current = setInterval(loadStatus, interval)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [loadStatus, runningNow])

  useEffect(() => {
    api.profiles.list().then(setProfiles).catch(console.error)
    loadStatus()
  }, [loadStatus])

  // Tick the countdown every 30s
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 30_000)
    return () => clearInterval(id)
  }, [])

  const setDraftField = <K extends keyof ScheduleRequest>(k: K, v: ScheduleRequest[K]) =>
    setDraft(d => d ? { ...d, [k]: v } : d)

  const toggleProfile = (id: string) => {
    if (!draft) return
    const next = draft.profile_ids.includes(id)
      ? draft.profile_ids.filter(p => p !== id)
      : [...draft.profile_ids, id]
    setDraftField('profile_ids', next)
  }

  const handleSave = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await api.schedule.update(draft)
      setStatus(updated)
      setDraft({
        enabled:        updated.enabled,
        interval_hours: updated.interval_hours,
        schedule_time:  updated.schedule_time ?? '',
        profile_ids:    updated.profile_ids,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleRunNow = async () => {
    setRunNowError(null)
    try {
      const { job_id } = await api.schedule.runNow()
      setRunningNow(job_id)
      loadStatus()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Run failed'
      setRunNowError(msg)
    }
  }

  if (!draft) {
    if (error) {
      return (
        <div className="space-y-3 max-w-2xl">
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3 flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => { setError(null); loadStatus() }}
              className="ml-3 text-sm font-medium text-red-700 hover:text-red-900 underline"
            >
              Retry
            </button>
          </div>
        </div>
      )
    }
    return <div className="text-sm text-gray-400 text-center py-16">Loading…</div>
  }

  const isRunning    = !!(status?.running_job || runningNow)
  const isPreset     = INTERVAL_PRESETS.includes(draft.interval_hours)
  const allProfiles  = draft.profile_ids.length === 0
  const isDirty      = status && (
    draft.enabled        !== status.enabled        ||
    draft.interval_hours !== status.interval_hours ||
    (draft.schedule_time ?? '') !== (status.schedule_time ?? '') ||
    JSON.stringify([...draft.profile_ids].sort()) !== JSON.stringify([...status.profile_ids].sort())
  )

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Schedule</h1>
          <p className="text-xs text-gray-400 mt-0.5">Runs automatically while the app is open in the system tray.</p>
        </div>
        <div className="flex items-center gap-3">
          {saved && <span className="text-xs text-emerald-600">✓ Saved</span>}
          {isDirty && !saved && <span className="text-xs text-amber-500">Unsaved changes</span>}
          <button
            onClick={handleSave}
            disabled={saving || !isDirty}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-md hover:bg-brand-700 disabled:opacity-40"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-2 font-bold">×</button>
        </div>
      )}

      {/* Live status card */}
      <section className="bg-white border border-gray-200 rounded-lg px-5 py-4 space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-gray-100">
          <h2 className="text-sm font-medium text-gray-700">Status</h2>
          <button
            onClick={handleRunNow}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning
              ? <><span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" /> Running…</>
              : '▶ Run Now'
            }
          </button>
        </div>

        {runNowError && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2 flex justify-between">
            {runNowError}
            <button onClick={() => setRunNowError(null)} className="ml-2 font-bold">×</button>
          </div>
        )}

        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Scheduler</span>
          {status?.enabled
            ? <span className="flex items-center gap-1.5 text-sm font-medium text-green-700">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                Active
              </span>
            : <span className="flex items-center gap-1.5 text-sm text-gray-400">
                <span className="w-2 h-2 rounded-full bg-gray-300" />
                Inactive
              </span>
          }
        </div>

        {status?.enabled && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Next run</span>
            <span className="text-sm font-medium text-gray-900" key={tick}>
              {formatCountdown(status.next_run_at)}
              {status.next_run_at && (
                <span className="text-xs text-gray-400 ml-2">({formatTime(status.next_run_at)})</span>
              )}
            </span>
          </div>
        )}

        {status?.running_job && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Running now</span>
            <span className="flex items-center gap-1.5 text-sm text-brand-600 font-medium">
              <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
              Job in progress
            </span>
          </div>
        )}

        {status?.last_run_at && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Last run</span>
            <span className="flex items-center gap-2 text-sm text-gray-500">
              {formatTime(status.last_run_at)}
              <StatusBadge status={status.last_status} />
            </span>
          </div>
        )}
      </section>

      {/* Configuration */}
      <section className="bg-white border border-gray-200 rounded-lg px-5 py-4 space-y-5">
        <h2 className="text-sm font-medium text-gray-700 pb-2 border-b border-gray-100">Configuration</h2>

        {/* Enable toggle */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-gray-800">Enable automatic scheduling</div>
            <div className="text-xs text-gray-400 mt-0.5">Runs will fire while the backend is running</div>
          </div>
          <button
            type="button"
            onClick={() => setDraftField('enabled', !draft.enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              draft.enabled ? 'bg-brand-600' : 'bg-gray-200'
            }`}
          >
            <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
              draft.enabled ? 'translate-x-6' : 'translate-x-1'
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
                onClick={() => { setDraftField('interval_hours', h); setCustom('') }}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  draft.interval_hours === h && isPreset
                    ? 'bg-brand-600 text-white border-brand-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-brand-400'
                }`}
              >
                {h}h
              </button>
            ))}
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={1}
                max={8760}
                placeholder="Custom"
                value={customHours}
                onChange={e => {
                  setCustom(e.target.value)
                  const n = parseInt(e.target.value, 10)
                  if (!isNaN(n) && n >= 1) setDraftField('interval_hours', n)
                }}
                className={`w-24 rounded-md border px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                  !isPreset ? 'border-brand-400 ring-1 ring-brand-300' : 'border-gray-300'
                }`}
              />
              {!isPreset && customHours === '' && (
                <span className="text-xs text-brand-600">{draft.interval_hours}h (custom)</span>
              )}
            </div>
          </div>
        </div>

        {/* Scheduled time */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Run at (optional)</label>
          <p className="text-xs text-gray-400 mb-2">
            Run at a specific time of day. Leave empty to run on interval alone.
          </p>
          <input
            type="time"
            value={draft.schedule_time}
            onChange={e => setDraftField('schedule_time', e.target.value)}
            className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          {draft.schedule_time && (
            <button
              type="button"
              onClick={() => setDraftField('schedule_time', '')}
              className="ml-2 text-xs text-gray-400 hover:text-gray-600 underline"
            >
              Clear
            </button>
          )}
        </div>

        {/* Profiles */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-2">Profiles to run</label>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={allProfiles}
                onChange={() => setDraftField('profile_ids', [])}
              />
              <span className="font-medium">All profiles</span>
            </label>
            {profiles.map(p => (
              <label key={p.profile_id} className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer ml-4">
                <input
                  type="checkbox"
                  checked={!allProfiles && draft.profile_ids.includes(p.profile_id)}
                  onChange={() => toggleProfile(p.profile_id)}
                />
                <span>{p.label}</span>
                <span className="text-xs text-gray-400">
                  {p.vehicles.map(v => v.join(' ')).join(' · ')}
                </span>
              </label>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
