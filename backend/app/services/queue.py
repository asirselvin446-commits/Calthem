"""Bulk call queue with configurable concurrency and retry logic.

Runs as an in-process asyncio background task per campaign. Never launches all
calls at once — a semaphore bounds concurrency (default 1 for the exhibition
demo). Failed/unanswered contacts are retried up to the campaign's max_retries.
One contact failing never aborts the campaign.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from ..config import settings
from ..db import SessionLocal
from ..models import (
    Campaign, Contact, Call, CampaignStatus, ContactStatus, CallStatus,
)
from .adapters import get_adapter
from .events import bus

# Contact statuses eligible for a retry pass.
_RETRYABLE = {ContactStatus.NO_ANSWER, ContactStatus.BUSY, ContactStatus.FAILED}

# Track running campaigns so we don't double-start.
_running: dict[str, asyncio.Task] = {}


def is_running(campaign_id: str) -> bool:
    task = _running.get(campaign_id)
    return task is not None and not task.done()


def start_campaign(campaign_id: str) -> bool:
    """Kick off (or resume) a campaign's queue. Returns False if already running."""
    if is_running(campaign_id):
        return False
    task = asyncio.create_task(_run_campaign(campaign_id))
    _running[campaign_id] = task
    return True


def stop_campaign(campaign_id: str) -> None:
    task = _running.get(campaign_id)
    if task and not task.done():
        task.cancel()


async def run_single_call(call_id: str) -> None:
    """Run one already-created call (single-call mode)."""
    await get_adapter().run_call(call_id)


async def _run_campaign(campaign_id: str) -> None:
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            return
        campaign.status = CampaignStatus.RUNNING
        db.commit()
        bus.publish({"type": "campaign_update", "campaign_id": campaign_id,
                     "status": CampaignStatus.RUNNING})

        concurrency = max(campaign.concurrency or settings.MAX_CONCURRENCY, 1)
        max_retries = campaign.max_retries if campaign.max_retries is not None else settings.MAX_RETRIES
    finally:
        db.close()

    adapter = get_adapter()

    for attempt in range(max_retries + 1):
        # Gather the pending/retryable contact ids for this pass.
        db = SessionLocal()
        try:
            if attempt == 0:
                contacts = (
                    db.query(Contact)
                    .filter(Contact.campaign_id == campaign_id,
                            Contact.status == ContactStatus.PENDING)
                    .all()
                )
            else:
                contacts = (
                    db.query(Contact)
                    .filter(Contact.campaign_id == campaign_id,
                            Contact.status.in_(list(_RETRYABLE)),
                            Contact.phone_valid == True)  # noqa: E712
                    .all()
                )
            contact_ids = [c.id for c in contacts]
        finally:
            db.close()

        if not contact_ids:
            break
        if attempt > 0:
            await asyncio.sleep(settings.RETRY_DELAY_SECONDS)

        sem = asyncio.Semaphore(concurrency)

        async def _one(contact_id: str) -> None:
            async with sem:
                call_id = _create_call(campaign_id, contact_id)
                if call_id:
                    try:
                        await adapter.run_call(call_id)
                    except Exception as exc:
                        _mark_call_failed(call_id, str(exc))

        try:
            await asyncio.gather(*(_one(cid) for cid in contact_ids))
        except asyncio.CancelledError:
            _set_campaign_status(campaign_id, CampaignStatus.PAUSED)
            raise

    _finalize_campaign(campaign_id)


def _create_call(campaign_id: str, contact_id: str) -> str | None:
    db = SessionLocal()
    try:
        contact = db.get(Contact, contact_id)
        if contact is None:
            return None
        contact.attempts += 1
        call = Call(campaign_id=campaign_id, contact_id=contact_id, phone=contact.phone,
                    status=CallStatus.PREPARING)
        db.add(call)
        db.commit()
        db.refresh(call)
        return call.id
    finally:
        db.close()


def _mark_call_failed(call_id: str, error: str) -> None:
    db = SessionLocal()
    try:
        call = db.get(Call, call_id)
        if call:
            call.status = CallStatus.FAILED
            call.error = error
            call.ended_at = datetime.utcnow()
            contact = db.get(Contact, call.contact_id)
            if contact:
                contact.status = ContactStatus.FAILED
            db.commit()
    finally:
        db.close()


def _set_campaign_status(campaign_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            campaign.status = status
            db.commit()
        bus.publish({"type": "campaign_update", "campaign_id": campaign_id, "status": status})
    finally:
        db.close()


def _finalize_campaign(campaign_id: str) -> None:
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            campaign.status = CampaignStatus.COMPLETED
            db.commit()
        bus.publish({"type": "campaign_update", "campaign_id": campaign_id,
                     "status": CampaignStatus.COMPLETED})
    finally:
        db.close()
