"""
Multi-schedule async scheduler for IngenuityAI.

Each schedule entry stored in dashboard_settings.json under "schedules" drives
its own independent asyncio task. State (next_run_at, last_run_at, etc.) is
held in-memory per schedule; persistent config lives in the settings file.

Lifecycle is managed by the FastAPI lifespan handler in app.py:
    startup()  → reads persisted entries, starts tasks for enabled ones
    shutdown() → cancels all loop tasks cleanly
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


@dataclass
class _ScheduleState:
    task: "asyncio.Task | None" = None
    next_run_at: "datetime | None" = None
    last_run_at: "str | None" = None
    last_job_id: "str | None" = None
    last_status: "str | None" = None


# schedule_id → runtime state
_states: dict[str, _ScheduleState] = {}


# ── Public API ─────────────────────────────────────────────────────────────────

def get_all_statuses() -> list[dict]:
    return [_entry_status(e) for e in _load_entries()]


def get_status(schedule_id: str) -> "dict | None":
    entry = _find_entry(schedule_id)
    return _entry_status(entry) if entry else None


async def startup() -> None:
    try:
        from storage import history_db
        history_db.init_db()
    except Exception as exc:
        log.warning("Scheduler: could not init DB: %s", exc)

    for entry in _load_entries():
        sid = entry["id"]
        _states.setdefault(sid, _ScheduleState())
        if entry.get("enabled"):
            _schedule_next(sid)
            _spawn_task(sid)
            log.info(
                "Scheduler[%s]: started (interval=%dh, time=%r, next=%s)",
                sid,
                entry.get("interval_hours", 24),
                entry.get("schedule_time", ""),
                _states[sid].next_run_at.isoformat() if _states[sid].next_run_at else "?",
            )


async def shutdown() -> None:
    for sid, state in list(_states.items()):
        if state.task and not state.task.done():
            state.task.cancel()
            try:
                await state.task
            except asyncio.CancelledError:
                pass
            state.task = None


async def apply_entry(entry: dict) -> dict:
    """Create or update a schedule entry. Returns the full status dict."""
    sid = entry["id"]
    entries = _load_entries()
    idx = next((i for i, e in enumerate(entries) if e["id"] == sid), None)
    if idx is not None:
        entries[idx] = entry
    else:
        entries.append(entry)
    _save_entries(entries)

    _states.setdefault(sid, _ScheduleState())
    state = _states[sid]
    if state.task and not state.task.done():
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass
        state.task = None

    if entry.get("enabled"):
        _schedule_next(sid)
        _spawn_task(sid)

    return _entry_status(entry)


async def delete_entry(schedule_id: str) -> bool:
    entries = _load_entries()
    new_entries = [e for e in entries if e["id"] != schedule_id]
    if len(new_entries) == len(entries):
        return False
    _save_entries(new_entries)

    state = _states.pop(schedule_id, None)
    if state and state.task and not state.task.done():
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass
    return True


async def run_now(schedule_id: str) -> str:
    """Fire an immediate run for a schedule. Returns job_id."""
    from dashboard.backend.job_manager import create_job, RunOptions

    entry = _find_entry(schedule_id)
    profile_ids = list(entry.get("profile_ids", [])) if entry else []
    options = RunOptions(
        profile_ids=profile_ids,
        dry_run=False, no_llm=False, backend=None,
        force_email=False, no_email=False, debug=False,
    )
    job = create_job(profile_ids, options)
    asyncio.ensure_future(_launch_and_track(schedule_id, job.job_id))
    return job.job_id


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_entries() -> list[dict]:
    from dashboard.backend import settings_store
    return list(settings_store.get("schedules") or [])


def _save_entries(entries: list[dict]) -> None:
    from dashboard.backend import settings_store
    settings_store.save({"schedules": entries})


def _find_entry(schedule_id: str) -> "dict | None":
    return next((e for e in _load_entries() if e["id"] == schedule_id), None)


def _entry_status(entry: dict) -> dict:
    from dashboard.backend.job_manager import get_job
    sid = entry["id"]
    state = _states.get(sid, _ScheduleState())

    running_job = None
    if state.last_job_id:
        job = get_job(state.last_job_id)
        if job and job.status in ("pending", "running"):
            running_job = {
                "job_id":     job.job_id,
                "status":     job.status,
                "started_at": job.started_at,
            }

    return {
        **entry,
        "next_run_at": state.next_run_at.isoformat() if state.next_run_at else None,
        "last_run_at": state.last_run_at,
        "last_job_id": state.last_job_id,
        "last_status": state.last_status,
        "running_job": running_job,
        "task_alive":  state.task is not None and not state.task.done(),
    }


def _schedule_next(schedule_id: str) -> None:
    entry = _find_entry(schedule_id)
    if not entry:
        return
    state = _states.setdefault(schedule_id, _ScheduleState())
    now = datetime.now(timezone.utc)
    min_delay = timedelta(seconds=30)
    schedule_time = entry.get("schedule_time", "")
    interval_h = int(entry.get("interval_hours", 24))

    if schedule_time:
        state.next_run_at = _next_time_of_day(schedule_time, interval_h, now, min_delay)
        return

    interval = timedelta(hours=interval_h)
    if state.last_run_at:
        try:
            last = datetime.fromisoformat(state.last_run_at.replace("Z", "+00:00"))
            candidate = last + interval
            missed = False
            while candidate <= now:
                candidate += interval
                missed = True
            state.next_run_at = now + timedelta(seconds=5) if missed else max(candidate, now + min_delay)
            return
        except Exception:
            pass

    state.next_run_at = now + interval


def _next_time_of_day(
    schedule_time: str,
    interval_hours: int,
    now: datetime,
    min_delay: timedelta,
) -> datetime:
    try:
        h, m = (int(x) for x in schedule_time.split(":"))
    except Exception:
        return now + timedelta(hours=interval_hours)

    local_now = datetime.now()
    candidate = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
    step = (
        timedelta(days=interval_hours // 24)
        if interval_hours % 24 == 0
        else timedelta(hours=interval_hours)
    )
    while candidate <= local_now:
        candidate += step

    try:
        candidate_utc = candidate.astimezone(timezone.utc)
    except Exception:
        candidate_utc = now + timedelta(hours=interval_hours)

    return max(candidate_utc, now + min_delay)


def _spawn_task(schedule_id: str) -> None:
    state = _states.setdefault(schedule_id, _ScheduleState())
    state.task = asyncio.ensure_future(_run_loop(schedule_id))


async def _run_loop(schedule_id: str) -> None:
    state = _states.get(schedule_id)
    if not state:
        return

    log.info(
        "Scheduler[%s]: loop started — next=%s",
        schedule_id,
        state.next_run_at.isoformat() if state.next_run_at else "?",
    )

    try:
        while True:
            await asyncio.sleep(15)

            entry = _find_entry(schedule_id)
            if not entry or not entry.get("enabled"):
                log.info("Scheduler[%s]: disabled — loop exiting", schedule_id)
                break

            if state.next_run_at and datetime.now(timezone.utc) >= state.next_run_at:
                log.info("Scheduler[%s]: firing scheduled run", schedule_id)
                try:
                    job_id, status = await _fire_and_wait(schedule_id)
                    state.last_job_id = job_id
                    state.last_run_at = datetime.now(timezone.utc).isoformat()
                    state.last_status = status
                    log.info("Scheduler[%s]: job %s finished — %s", schedule_id, job_id, status)
                except Exception as exc:
                    log.error("Scheduler[%s]: job raised: %s", schedule_id, exc)
                    state.last_status = "error"

                _schedule_next(schedule_id)
                log.info(
                    "Scheduler[%s]: next run at %s",
                    schedule_id,
                    state.next_run_at.isoformat() if state.next_run_at else "?",
                )

    except asyncio.CancelledError:
        log.info("Scheduler[%s]: loop cancelled", schedule_id)
        raise


async def _fire_and_wait(schedule_id: str) -> tuple[str, str]:
    from dashboard.backend.job_manager import create_job, launch_job, get_job, RunOptions

    entry = _find_entry(schedule_id)
    profile_ids = list(entry.get("profile_ids", [])) if entry else []
    options = RunOptions(
        profile_ids=profile_ids,
        dry_run=False, no_llm=False, backend=None,
        force_email=False, no_email=False, debug=False,
    )
    job = create_job(profile_ids, options)
    await launch_job(job.job_id)
    finished = get_job(job.job_id)
    return job.job_id, (finished.status if finished else "unknown")


async def _launch_and_track(schedule_id: str, job_id: str) -> None:
    from dashboard.backend.job_manager import launch_job, get_job

    state = _states.get(schedule_id)
    if state:
        state.last_job_id = job_id
    try:
        await launch_job(job_id)
    except Exception as exc:
        log.error("Scheduler[%s]: run-now job %s raised: %s", schedule_id, job_id, exc)

    job = get_job(job_id)
    if state:
        state.last_run_at = datetime.now(timezone.utc).isoformat()
        state.last_status = job.status if job else "unknown"

    entry = _find_entry(schedule_id)
    if entry and entry.get("enabled"):
        _schedule_next(schedule_id)
        log.info(
            "Scheduler[%s]: next run rescheduled to %s",
            schedule_id,
            _states[schedule_id].next_run_at.isoformat() if _states.get(schedule_id, _ScheduleState()).next_run_at else "?",
        )
