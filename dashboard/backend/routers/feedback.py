"""
Feedback router — portal users submit beta feedback that is emailed to the owner.

POST /portal/feedback
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dashboard.backend.auth_deps import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/portal/feedback", tags=["feedback"])

_CATEGORIES = {"Bug Report", "Feature Request", "General", "Other"}


class FeedbackRequest(BaseModel):
    category: str = Field(..., description="One of: Bug Report, Feature Request, General, Other")
    message:  str = Field(..., min_length=5, max_length=5000)
    rating:   int | None = Field(None, ge=1, le=5)


@router.post("", status_code=202)
def submit_feedback(req: FeedbackRequest, current_user=Depends(get_current_user)):
    """Receive feedback from a portal user and email it to the configured address."""
    if req.category not in _CATEGORIES:
        raise HTTPException(422, f"category must be one of: {', '.join(sorted(_CATEGORIES))}")

    import config
    from notifications.email_alert import send_feedback_email

    to = config.FEEDBACK_EMAIL_TO
    if not to:
        log.warning("Feedback received but FEEDBACK_EMAIL_TO is not configured — dropping")
        return {"status": "received", "emailed": False}

    ok = send_feedback_email(
        username=current_user.username,
        category=req.category,
        message=req.message.strip(),
        rating=req.rating,
        to_address=to,
    )

    if not ok:
        log.warning(
            "Feedback from %s queued but email send failed (Gmail not configured?)",
            current_user.username,
        )

    return {"status": "received", "emailed": ok}
