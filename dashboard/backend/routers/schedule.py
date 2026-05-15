"""
Schedules router — CRUD for multiple named schedules.
"""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/schedules", tags=["schedules"])


class ScheduleEntryRequest(BaseModel):
    label:          str       = "My Schedule"
    enabled:        bool      = True
    interval_hours: int       = Field(default=24, ge=1, le=8760)
    schedule_time:  str       = ""        # "HH:MM" local time, empty = interval-only
    profile_ids:    list[str] = []        # empty = run all profiles


@router.get("")
def list_schedules():
    from dashboard.backend import app_scheduler
    return {"schedules": app_scheduler.get_all_statuses()}


@router.post("", status_code=201)
async def create_schedule(req: ScheduleEntryRequest):
    from dashboard.backend import app_scheduler
    entry = {**req.model_dump(), "id": str(uuid.uuid4())}
    return await app_scheduler.apply_entry(entry)


@router.get("/{schedule_id}")
def get_schedule(schedule_id: str):
    from dashboard.backend import app_scheduler
    status = app_scheduler.get_status(schedule_id)
    if not status:
        raise HTTPException(404, "Schedule not found")
    return status


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: str, req: ScheduleEntryRequest):
    from dashboard.backend import app_scheduler
    if not app_scheduler.get_status(schedule_id):
        raise HTTPException(404, "Schedule not found")
    entry = {**req.model_dump(), "id": schedule_id}
    return await app_scheduler.apply_entry(entry)


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str):
    from dashboard.backend import app_scheduler
    if not await app_scheduler.delete_entry(schedule_id):
        raise HTTPException(404, "Schedule not found")


@router.post("/{schedule_id}/run-now")
async def run_schedule_now(schedule_id: str):
    from dashboard.backend import app_scheduler
    from dashboard.backend.job_manager import list_jobs

    if not app_scheduler.get_status(schedule_id):
        raise HTTPException(404, "Schedule not found")

    active = [j for j in list_jobs() if j.status in ("pending", "running")]
    if active:
        raise HTTPException(409, f"A run is already in progress (job_id={active[0].job_id})")

    job_id = await app_scheduler.run_now(schedule_id)
    return {"job_id": job_id}
