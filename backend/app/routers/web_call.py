"""Web voice call — a real browser<->Bolna conversation, no telephony.

Flow:
  1. POST /api/web-call/start {instruction, ...} -> Calthem generates the schema,
     creates a Campaign+Contact+Call, builds a web agent config (input/output
     provider "default") and registers it on the Bolna engine.
  2. Returns {call_id, agent_id, ws_url}. The BROWSER then connects directly to
     ws_url, streams 16kHz mic PCM, and plays back 24kHz PCM.
  3. At end of call the engine's extraction+webhook tasks POST results to
     /api/webhooks/bolna?call_id=... which finalizes the Call.
  4. The browser also POSTs the transcript it captured via /transcript.
"""
from __future__ import annotations

from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Campaign, Contact, Call, CampaignStatus, CallStatus, CallState, ContactStatus
from ..services.instruction_compiler import generate_schema, build_web_agent_config
from ..services.events import bus

router = APIRouter(prefix="/api/web-call", tags=["web-call"])


class WebCallStart(BaseModel):
    instruction: str
    name: str = ""
    organisation: str = ""
    language: str = "en"


@router.post("/start")
async def start_web_call(payload: WebCallStart, db: Session = Depends(get_db)) -> dict:
    if payload.instruction.strip().__len__() < 6:
        raise HTTPException(status_code=400, detail="Describe what to collect.")

    schema = await generate_schema(payload.instruction)

    campaign = Campaign(
        name=f"Web call · {payload.name or 'guest'}",
        mode="web",
        instruction=payload.instruction,
        extraction_schema=schema,
        organisation=payload.organisation,
        language=payload.language,
        status=CampaignStatus.RUNNING,
    )
    db.add(campaign)
    db.flush()

    contact = Contact(campaign_id=campaign.id, name=payload.name or "Web guest",
                      phone="web", phone_valid=True, status=ContactStatus.CALLING)
    db.add(contact)
    db.flush()

    call = Call(campaign_id=campaign.id, contact_id=contact.id, phone="web",
                status=CallStatus.CONNECTED, state=CallState.CONNECTED,
                started_at=datetime.utcnow())
    db.add(call)
    db.commit()
    db.refresh(call)

    webhook_url = f"{settings.CALTHEM_WEBHOOK_BASE.rstrip('/')}/api/webhooks/bolna?call_id={call.id}"
    config = build_web_agent_config(
        name=campaign.name,
        instruction=payload.instruction,
        schema=schema,
        organisation=payload.organisation,
        language=payload.language,
        webhook_url=webhook_url,
        webhook_in_config=settings.bolna_hosted,
    )

    # Register the agent on the Bolna engine (self-hosted) or Bolna cloud.
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.bolna_agent_endpoint(), json=config, headers=settings.bolna_headers()
            )
            resp.raise_for_status()
            agent_id = resp.json().get("agent_id")
    except Exception as exc:
        call.status = CallStatus.FAILED
        call.error = f"Could not reach Bolna engine at {settings.BOLNA_API_URL}: {exc}"
        contact.status = ContactStatus.FAILED
        campaign.status = CampaignStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=(f"Bolna engine not reachable at {settings.BOLNA_API_URL}. "
                    "Start it: cd calthem/bolna_runtime && "
                    "../../bolna/.venv/Scripts/python.exe server.py"),
        )

    campaign.agent_id = agent_id
    db.commit()

    ws_url = f"{settings.BOLNA_WS_URL.rstrip('/')}/chat/v1/{agent_id}"
    return {
        "call_id": call.id,
        "campaign_id": campaign.id,
        "agent_id": agent_id,
        "ws_url": ws_url,
        "extraction_schema": schema,
        "welcome": config["agent_config"]["agent_welcome_message"],
    }


class TranscriptUpdate(BaseModel):
    transcript: list[dict] = []
    status: str = "completed"
    duration: float = 0.0


@router.post("/{call_id}/finish")
async def finish_web_call(call_id: str, payload: TranscriptUpdate = Body(...),
                          db: Session = Depends(get_db)) -> dict:
    """Called by the browser when the web call ends: saves the transcript it
    captured and marks the call completed (extraction may still arrive via
    the webhook and merge in)."""
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if payload.transcript:
        call.transcript = payload.transcript
    call.duration = payload.duration or call.duration
    call.ended_at = datetime.utcnow()
    if call.status not in (CallStatus.COMPLETED,):
        call.status = CallStatus.COMPLETED if payload.status == "completed" else CallStatus.FAILED
    call.state = CallState.COMPLETED
    contact = db.get(Contact, call.contact_id)
    if contact and contact.status not in (ContactStatus.COMPLETED,):
        contact.status = ContactStatus.COMPLETED
    campaign = db.get(Campaign, call.campaign_id)
    if campaign:
        campaign.status = CampaignStatus.COMPLETED
    db.commit()
    bus.publish({"type": "call_update", "call_id": call.id, "campaign_id": call.campaign_id,
                 "contact_id": call.contact_id, "contact_name": contact.name if contact else "",
                 "status": call.status, "state": call.state, "duration": call.duration,
                 "feed": True, "ts": datetime.utcnow().isoformat()})
    return {"ok": True, "call_id": call.id}
