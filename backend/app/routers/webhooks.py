"""Receives call-progress + completion data from Bolna (real mode).

Bolna POSTs the full execution object to the webhook on each status change. The
payload matches Bolna's Get-Execution API: top-level `id` (execution id),
`status`, `transcript` (a string "assistant: ...\\nuser: ..."), `extracted_data`
(may be null), and `telephony_data` {to_number, from_number, duration, ...}.

We correlate it back to a Calthem Call (by execution id, our echoed call_id, or
phone), save the transcript, and — since hosted Bolna may not return structured
extraction — extract the schema fields from the transcript ourselves.
"""
from __future__ import annotations

import re
from datetime import datetime

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Call, Contact, Campaign, CallStatus, CallState, ContactStatus
from ..services.events import bus
from ..services.instruction_compiler import extract_from_transcript

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Statuses that mean the call is over (Bolna posts several events per call).
_TERMINAL = {
    "completed", "call-disconnected", "call_disconnected", "disconnected",
    "failed", "error", "no-answer", "no_answer", "noanswer", "busy", "canceled",
    "cancelled",
}


def _get(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", {}, []):
            return v
    return None


@router.post("/bolna")
async def bolna_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "reason": "bad payload"}

    tele = body.get("telephony_data") or {}
    ctx = body.get("context_details") or body.get("context_data") or {}
    user_data = body.get("user_data") or {}

    # Bolna's execution id (top-level "id"); we store it on the Call as provider_call_id.
    execution_id = _get(body, "id", "execution_id")

    # --- Correlate the webhook to a Calthem Call ---
    call_id = (
        request.query_params.get("call_id")
        or _get(body, "calthem_call_id")
        or user_data.get("calthem_call_id")
        or ctx.get("calthem_call_id")
    )
    call: Call | None = db.get(Call, call_id) if call_id else None

    if call is None and execution_id:
        call = (
            db.query(Call).filter(Call.provider_call_id == execution_id)
            .order_by(Call.created_at.desc()).first()
        )

    if call is None:
        phone = _get(body, "recipient_phone_number", "phone", "user_number") or tele.get("to_number")
        if phone:
            call = (
                db.query(Call)
                .filter(Call.phone == phone,
                        Call.status.notin_([CallStatus.COMPLETED, CallStatus.FAILED]))
                .order_by(Call.created_at.desc()).first()
            )
    if call is None:
        return {"ok": False, "reason": "no matching call"}

    # Remember the execution id for later webhook events on the same call.
    if execution_id and not call.provider_call_id:
        call.provider_call_id = execution_id

    status = str(body.get("status") or "").lower().strip()

    # --- Transcript (Bolna sends a string; also tolerate a list) ---
    raw_transcript = body.get("transcript") or body.get("messages")
    transcript_text = raw_transcript if isinstance(raw_transcript, str) else ""
    if raw_transcript:
        turns = _normalize_transcript(raw_transcript)
        if turns:
            call.transcript = turns
        if not transcript_text:
            transcript_text = "\n".join(f'{t["role"]}: {t["text"]}' for t in turns)

    # --- Structured extraction ---
    extracted = _get(body, "extracted_data", "extraction_data")
    if isinstance(extracted, dict) and extracted:
        merged = dict(call.extracted_data or {})
        merged.update(extracted)
        call.extracted_data = merged
    elif transcript_text and not (call.extracted_data or {}):
        # Hosted Bolna returned no structured data — extract from the transcript.
        campaign = db.get(Campaign, call.campaign_id)
        if campaign:
            mine = await extract_from_transcript(
                campaign.instruction, campaign.extraction_schema, transcript_text
            )
            if isinstance(mine, dict) and mine:
                call.extracted_data = {k: v for k, v in mine.items() if v is not None}

    call.recording_url = tele.get("recording_url") or body.get("recording_url") or call.recording_url
    call.duration = float(
        _get(tele, "duration") or _get(body, "duration", "conversation_duration") or call.duration or 0.0
    )

    contact = db.get(Contact, call.contact_id)

    # Non-terminal events (in-progress/queued/ringing): reflect liveness, don't finalize.
    if status and status not in _TERMINAL:
        call.state = CallState.CONNECTED
        if call.status in (CallStatus.PREPARING, CallStatus.CALLING):
            call.status = CallStatus.IN_PROGRESS
        db.commit()
        _publish(call, contact)
        return {"ok": True, "call_id": call.id, "stage": status or "update"}

    # Terminal — finalize.
    call.ended_at = datetime.utcnow()
    if status in ("no-answer", "no_answer", "noanswer"):
        call.status, cstatus = CallStatus.NO_ANSWER, ContactStatus.NO_ANSWER
    elif status == "busy":
        call.status, cstatus = CallStatus.BUSY, ContactStatus.BUSY
    elif status in ("failed", "error", "canceled", "cancelled"):
        call.status, cstatus = CallStatus.FAILED, ContactStatus.FAILED
    else:
        call.status, cstatus = CallStatus.COMPLETED, ContactStatus.COMPLETED
    call.state = CallState.COMPLETED
    if contact:
        contact.status = cstatus
    db.commit()

    _publish(call, contact, feed=True)
    return {"ok": True, "call_id": call.id}


def _publish(call: Call, contact: Contact | None, feed: bool = False) -> None:
    bus.publish({
        "type": "call_update", "call_id": call.id, "campaign_id": call.campaign_id,
        "contact_id": call.contact_id, "contact_name": contact.name if contact else "",
        "status": call.status, "state": call.state, "duration": call.duration,
        "feed": feed, "ts": datetime.utcnow().isoformat(),
    })


def _normalize_transcript(raw) -> list[dict]:
    """Accept Bolna's string transcript ("assistant: ..\\nuser: ..") or a list of
    {role, content} dicts, and return [{role: 'ai'|'person', text, ts}]."""
    out: list[dict] = []
    if isinstance(raw, str):
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^(assistant|agent|bot|ai|user|human|person|caller)\s*:\s*(.*)$",
                         line, re.IGNORECASE)
            if m:
                role = "ai" if m.group(1).lower() in ("assistant", "agent", "bot", "ai") else "person"
                out.append({"role": role, "text": m.group(2).strip(), "ts": None})
            elif out:
                out[-1]["text"] = (out[-1]["text"] + " " + line).strip()
        return out
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                role = item.get("role", "person")
                role = "ai" if role in ("assistant", "ai", "bot", "agent") else "person"
                out.append({"role": role,
                            "text": item.get("content") or item.get("text") or "",
                            "ts": item.get("ts")})
    return out
