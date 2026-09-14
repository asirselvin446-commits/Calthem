"""Dashboard overview metrics (monochrome glass cards)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..config import settings
from ..models import Campaign, Contact, Call, CallStatus

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    total_calls = db.query(func.count(Call.id)).scalar() or 0
    completed = db.query(func.count(Call.id)).filter(
        Call.status == CallStatus.COMPLETED).scalar() or 0
    failed = db.query(func.count(Call.id)).filter(
        Call.status.in_([CallStatus.FAILED, CallStatus.NO_ANSWER, CallStatus.BUSY])
    ).scalar() or 0
    avg_duration = db.query(func.avg(Call.duration)).filter(
        Call.status == CallStatus.COMPLETED).scalar() or 0.0
    campaigns = db.query(func.count(Campaign.id)).scalar() or 0
    contacts = db.query(func.count(Contact.id)).scalar() or 0

    # "Information collected" = count of completed calls with non-empty extraction.
    collected = 0
    for (data,) in db.query(Call.extracted_data).filter(
            Call.status == CallStatus.COMPLETED).all():
        if data:
            collected += 1

    return {
        "app": settings.APP_NAME,
        "tagline": settings.TAGLINE,
        "adapter": settings.TELEPHONY_ADAPTER,
        "metrics": {
            "total_calls": total_calls,
            "completed": completed,
            "successful": completed,
            "failed": failed,
            "avg_duration": round(float(avg_duration), 1),
            "information_collected": collected,
            "campaigns": campaigns,
            "contacts": contacts,
        },
    }
