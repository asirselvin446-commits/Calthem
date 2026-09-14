"""Calls: single-call quick start, listing, and call detail."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Campaign, Contact, Call, CallStatus, ContactStatus
from ..schemas import SingleCallRequest, CallOut, CallDetail
from ..services.campaign_service import create_campaign
from ..services import queue

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.post("/single")
async def start_single_call(payload: SingleCallRequest, db: Session = Depends(get_db)) -> dict:
    """Create a one-contact campaign and immediately place the call (Mode A)."""
    campaign = await create_campaign(
        db,
        name=f"Single call · {payload.name or payload.phone}",
        mode="single",
        instruction=payload.instruction,
        organisation=payload.organisation,
        voice=payload.voice,
        language=payload.language,
        max_duration=payload.max_duration,
        concurrency=1,
        max_retries=0,
        contacts=[{"name": payload.name, "phone": payload.phone}],
    )
    contact = db.query(Contact).filter(Contact.campaign_id == campaign.id).first()
    if not contact:
        raise HTTPException(status_code=400, detail="Could not create contact")
    if not contact.phone_valid:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    call = Call(campaign_id=campaign.id, contact_id=contact.id, phone=contact.phone,
                status=CallStatus.PREPARING)
    contact.status = ContactStatus.CALLING
    contact.attempts += 1
    db.add(call)
    db.commit()
    db.refresh(call)

    # Fire-and-forget: the call runs asynchronously (never block the request).
    asyncio.create_task(queue.run_single_call(call.id))

    return {
        "campaign_id": campaign.id,
        "call_id": call.id,
        "contact_id": contact.id,
        "extraction_schema": campaign.extraction_schema,
        "status": call.status,
    }


@router.get("/{call_id}", response_model=CallDetail)
def get_call(call_id: str, db: Session = Depends(get_db)) -> CallDetail:
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    contact = db.get(Contact, call.contact_id)
    return CallDetail(
        **CallOut.model_validate(call).model_dump(),
        transcript=call.transcript or [],
        contact_name=contact.name if contact else "",
    )


@router.get("", response_model=list[CallOut])
def list_calls(campaign_id: str = Query(...), db: Session = Depends(get_db),
               limit: int = Query(100, le=500), offset: int = 0) -> list[Call]:
    return (
        db.query(Call)
        .filter(Call.campaign_id == campaign_id)
        .order_by(Call.created_at.desc())
        .offset(offset).limit(limit).all()
    )
