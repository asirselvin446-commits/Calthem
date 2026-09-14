"""Campaign CRUD, start/pause, stats, and contact listing."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Campaign, Contact, CampaignStatus
from ..schemas import (
    CampaignCreate, CampaignOut, CampaignDetail, CampaignStats, ContactOut,
)
from ..services.campaign_service import create_campaign, compute_stats
from ..services import queue

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut)
async def create(payload: CampaignCreate, db: Session = Depends(get_db)) -> Campaign:
    campaign = await create_campaign(
        db,
        name=payload.name,
        mode=payload.mode,
        instruction=payload.instruction,
        organisation=payload.organisation,
        voice=payload.voice,
        language=payload.language,
        max_duration=payload.max_duration,
        concurrency=payload.concurrency,
        max_retries=payload.max_retries,
        contacts=[c.model_dump() for c in payload.contacts],
    )
    return campaign


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), limit: int = Query(50, le=200),
                   offset: int = 0) -> list[Campaign]:
    return (
        db.query(Campaign)
        .order_by(Campaign.created_at.desc())
        .offset(offset).limit(limit).all()
    )


@router.get("/{campaign_id}", response_model=CampaignDetail)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)) -> CampaignDetail:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    stats = compute_stats(db, campaign_id)
    return CampaignDetail(
        **CampaignOut.model_validate(campaign).model_dump(),
        stats=CampaignStats(**stats),
        contact_count=stats["total"],
    )


@router.get("/{campaign_id}/contacts", response_model=list[ContactOut])
def list_contacts(campaign_id: str, db: Session = Depends(get_db),
                  limit: int = Query(100, le=500), offset: int = 0) -> list[Contact]:
    if not db.get(Campaign, campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    return (
        db.query(Contact)
        .filter(Contact.campaign_id == campaign_id)
        .offset(offset).limit(limit).all()
    )


@router.post("/{campaign_id}/start")
async def start(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    started = queue.start_campaign(campaign_id)
    if not started:
        raise HTTPException(status_code=409, detail="Campaign already running")
    return {"campaign_id": campaign_id, "status": "running"}


@router.post("/{campaign_id}/pause")
def pause(campaign_id: str, db: Session = Depends(get_db)) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    queue.stop_campaign(campaign_id)
    campaign.status = CampaignStatus.PAUSED
    db.commit()
    return {"campaign_id": campaign_id, "status": "paused"}
