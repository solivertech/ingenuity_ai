"""
In-process async scheduler for IngenuityAI.

Runs a background asyncio task that polls every 15 s and fires a full
search+email job when the configured interval has elapsed.  State is held in
module-level variables (reset on process restart); persistent config
(enabled, interval, schedule_time, profile_ids) lives in dashboard_settings.json.

Lifecycle is managed by the FastAPI lifespan handler in app.py:
    startup()  → reads persisted config, starts loop if enabled
    shutdown() → cancels the loop task cleanly
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# ── Module-level state (in-memory only) ───────────────────────────────────────
_task: "asyncio.Task | None" = None
_next_run_at: "datetime | None" = None
_last_run_at: "str | None" = None   # ISO-8601, populated from DB on startup
_last_job_id: "str | None" = None
_last_status: "str | None" = None   # "complete" | "failed" | "cancelled"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_status() -> dict:
    """Return current scheduler state as a plain dict (safe to serialise to JSON)."""
    from dashboard.backend.job_manager import get_job

    running_job = None
    if _last_job_id:
        job = get_job(_last_job_id)
        if job and job.status in ("pending", "running"):
            running_job = {
                "job_id":     job.job_id,
                "status":     job.status,
                "started_at": job.started_at,
            }

    return {
        "enabled":        _is_enabled(),
        "interval_hours": _get_interval(),
        "schedule_time":  _get_schedule_time(),
        "profile_ids":    _get_profile_ids(),
        "next_run_at":    _next_run_at.isoformat() if _next_run_at else None,
        "last_run_at":    _last_run_at,
        "last_job_id":    _last_job_id,
        "last_status":    _last_status,
        "running_job":    running_job,
        "task_alive":     _task is not None and not _task.done(),
    }


async def startup() -> None:
    """
    Called by the FastAPI lifespan on backend start.
    Reads last-run time from the DB so the next-run calculation is accurate
    after a restart, then starts the loop if the schedule is enabled.
    """
    global _last_run_at

    try:
        from storage import history_db
        history_db.init_db()
        runs = history_db.get_history_summary()
        if runs:
            _last_run_at = runs[0]["run_at"]
    except Exception as exc:
        log.warning("Scheduler: could not read run history from DB: %s", exc)

    if _is_enabled():
        _schedule_next()
        _spawn_task()
        log.info(
            "Scheduler: auto-started (interval=%dh, time=%r, next=%s)",
            _get_interval(),
            _get_schedule_time(),
            _next_run_at.isoformat() if _next_run_at else "?",
        )
    else:
        log.debug("Scheduler: disabled — not starting loop")


async def shutdown() -> None:
    """Cancel the background loop and wait for it to exit cleanly."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None


async def apply_settings(
    enabled: bool,
    interval_hours: int,
    profile_ids: list[str],
    schedule_time: str = "",
) -> None:
    """
    Persist new schedule settings then restart the loop so changes take effect
    immediately without a backend restart.
    """
    from dashboard.backend import settings_store

    settings_store.save({
        "schedule_enabled":        enabled,
        "schedule_interval_hours": interval_hours,
        "schedule_profile_ids":    profile_ids,
        "schedule_time":           schedule_time,
    })

    await shutdown()

    if enabled:
        _schedule_next()
        _spawn_task()
        log.info(
            "Scheduler: (re)started — interval=%dh time=%r profiles=%s next=%s",
            interval_hours,
            schedule_time,
            profile_ids if profile_ids else "all",
            _next_run_at.isoformat() if _next_run_at else "?",
        )
    else:
        log.info("Scheduler: disabled")


async def run_now() -> str:
    """
    Fire an immediate run using the scheduled profile_ids.
    Returns the job_id immediately; the job runs in the background.
    Updates _last_run_at and recalculates _next_run_at when the job finishes.
    """
    from dashboard.backend.job_manager import create_job, RunOptions

    profile_ids = _get_profile_ids()
    options = RunOptions(
        profile_ids=profile_ids,
        dry_run=False,
        no_llm=False,
        backend=None,
        force_email=False,
        no_email=False,
        debug=False,
    )
    job = create_job(profile_ids, options)
    asyncio.ensure_future(_launch_and_track(job.job_id))
    return job.job_id


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_enabled() -> bool:
    from dashboard.backend import settings_store
    return bool(settings_store.get("schedule_enabled"))


def _get_interval() -> int:
    from dashboard.backend import settings_store
    return int(settings_store.get("schedule_interval_hours") or 24)


def _get_schedule_time() -> str:
    from dashboard.backend import settings_store
    return str(settings_store.get("schedule_time") or "")


def _get_profile_ids() -> list[str]:
    from dashboard.backend import settings_store
    return list(settings_store.get("schedule_profile_ids") or [])


def _schedule_next() -> None:
    """
    Compute and store the next fire time.

    If schedule_time is set ("HH:MM"), the next wall-clock occurrence of that
    local time is used, stepping by interval_hours (or 1 day for 24 h).

    Otherwise falls back to interval-from-last-run logic.  Missed intervals
    are detected and fire on the next poll (~15 s) rather than waiting another
    full cycle.  A 30-second minimum delay prevents an instant re-fire on
    settings changes.
    """
    global _next_run_at
    now           = datetime.now(timezone.utc)
    min_delay     = timedelta(seconds=30)
    schedule_time = _get_schedule_time()
    interval_h    = _get_interval()

    if schedule_time:
        _next_run_at = _next_time_of_day(schedule_time, interval_h, now, min_delay)
        return

    interval = timedelta(hours=interval_h)

    if _last_run_at:
        try:
            last      = datetime.fromisoformat(_last_run_at.replace("Z", "+00:00"))
            candidate = last + interval
            missed    = False
            while candidate <= now:
                candidate += interval
                missed = True
            if missed:
                # Fire on the next poll rather than waiting a full interval.
                _next_run_at = now + timedelta(seconds=5)
            else:
                _next_run_at = max(candidate, now + min_delay)
            return
        except Exception:
            pass

    # No history or parse error — wait one full interval from now.
    _next_run_at = now + interval


def _next_time_of_day(
    schedule_time: str,
    interval_hours: int,
    now: datetime,
    min_delay: timedelta,
) -> datetime:
    """Return the next UTC datetime when the local clock shows HH:MM."""
    try:
        h, m = (int(x) for x in schedule_time.split(":"))
    except Exception:
        return now + timedelta(hours=interval_hours)

    local_now = datetime.now()  # naive local time
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


def _spawn_task() -> None:
    global _task
    _task = asyncio.ensure_future(_run_loop())


async def _run_loop() -> None:
    """Poll every 15 s; fire a job when next_run_at is reached."""
    global _next_run_at, _last_run_at, _last_job_id, _last_status

    log.info(
        "Scheduler loop started — next run at %s",
        _next_run_at.isoformat() if _next_run_at else "?",
    )

    try:
        while True:
            await asyncio.sleep(15)

            if not _is_enabled():
                log.info("Scheduler: disabled — loop exiting")
                break

            if _next_run_at and datetime.now(timezone.utc) >= _next_run_at:
                log.info("Scheduler: firing scheduled run")
                try:
                    job_id, status = await _fire_and_wait()
                    _last_job_id = job_id
                    _last_run_at = datetime.now(timezone.utc).isoformat()
                    _last_status = status
                    log.info("Scheduler: job %s finished — %s", job_id, status)
                except Exception as exc:
                    log.error("Scheduler: job raised an exception: %s", exc)
                    _last_status = "error"

                _schedule_next()
                log.info("Scheduler: next run at %s", _next_run_at.isoformat() if _next_run_at else "?")

    except asyncio.CancelledError:
        log.info("Scheduler loop cancelled")
        raise


async def _fire_and_wait() -> tuple[str, str]:
    """Spawn main.py as a subprocess job and block until it exits."""
    from dashboard.backend.job_manager import create_job, launch_job, get_job, RunOptions

    profile_ids = _get_profile_ids()
    options     = RunOptions(
        profile_ids=profile_ids,
        dry_run=False,
        no_llm=False,
        backend=None,
        force_email=False,
        no_email=False,
        debug=False,
    )
    job = create_job(profile_ids, options)
    await launch_job(job.job_id)    # blocks until subprocess exits
    finished = get_job(job.job_id)
    return job.job_id, (finished.status if finished else "unknown")


async def _launch_and_track(job_id: str) -> None:
    """Launch a run-now job and update scheduler state when it finishes."""
    global _last_run_at, _last_job_id, _last_status
    from dashboard.backend.job_manager import launch_job, get_job

    _last_job_id = job_id
    try:
        await launch_job(job_id)
    except Exception as exc:
        log.error("Scheduler: run-now job %s raised: %s", job_id, exc)

    job = get_job(job_id)
    _last_run_at = datetime.now(timezone.utc).isoformat()
    _last_status = job.status if job else "unknown"
    log.info("Scheduler: run-now job %s finished — %s", job_id, _last_status)

    if _is_enabled():
        _schedule_next()
        log.info(
            "Scheduler: next run rescheduled to %s",
            _next_run_at.isoformat() if _next_run_at else "?",
        )
