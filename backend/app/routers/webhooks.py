"""Receives call-completion + extracted data from Bolna (real mode).

Bolna's webhook task POSTs the extracted JSON at end of call. We correlate it
back to a Calthem Call via calthem_call_id (passed as user_data) or by phone,
then finalize the Call and Contact rows.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Call, Contact, CallStatus, CallState, ContactStatus
from ..services.events import bus

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/bolna")
async def bolna_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    body = await request.json()

    # Correlation: query-param call_id (set on the webhook URL) is most reliable;
    # then explicit calthem_call_id in the body; finally a phone match.
    call_id = (
        request.query_params.get("call_id")
        or body.get("calthem_call_id")
        or (body.get("user_data") or {}).get("calthem_call_id")
        or (body.get("context_data") or {}).get("calthem_call_id")
    )
    call: Call | None = None
    if call_id:
        call = db.get(Call, call_id)
    # Hosted Bolna correlates by execution_id (stored on the Call as
    # provider_call_id when the call was placed).
    if call is None:
        execution_id = body.get("execution_id") or (body.get("data") or {}).get("execution_id")
        if execution_id:
            call = (
                db.query(Call)
                .filter(Call.provider_call_id == execution_id)
                .order_by(Call.created_at.desc())
                .first()
            )
    if call is None:
        phone = body.get("recipient_phone_number") or body.get("phone")
        if phone:
            call = (
                db.query(Call)
                .filter(Call.phone == phone,
                        Call.status.notin_([CallStatus.COMPLETED, CallStatus.FAILED]))
                .order_by(Call.created_at.desc())
                .first()
            )
    if call is None:
        return {"ok": False, "reason": "no matching call"}

    _META_KEYS = {
        "status", "transcript", "messages", "recording_url", "duration",
        "recipient_phone_number", "phone", "calthem_call_id", "user_data",
        "context_data", "execution_id", "agent_id", "call_sid", "conversation_time",
    }
    extracted = (
        body.get("extracted_data")
        or body.get("extraction_data")
        or body.get("data")
    )
    # Bolna's extraction webhook may POST the extracted fields as the body itself.
    if not extracted and isinstance(body, dict):
        extracted = {k: v for k, v in body.items() if k not in _META_KEYS}
    transcript = body.get("transcript") or body.get("messages") or []
    status = (body.get("status") or "completed").lower()

    if extracted and isinstance(extracted, dict):
        # Merge (don't clobber a transcript the browser already saved).
        merged = dict(call.extracted_data or {})
        merged.update(extracted)
        call.extracted_data = merged
    if transcript:
        call.transcript = _normalize_transcript(transcript)
    call.recording_url = body.get("recording_url") or call.recording_url
    call.duration = float(body.get("duration") or call.duration or 0.0)
    call.ended_at = datetime.utcnow()

    contact = db.get(Contact, call.contact_id)
    if status in ("no_answer", "no-answer", "noanswer"):
        call.status, cstatus = CallStatus.NO_ANSWER, ContactStatus.NO_ANSWER
    elif status == "busy":
        call.status, cstatus = CallStatus.BUSY, ContactStatus.BUSY
    elif status in ("failed", "error"):
        call.status, cstatus = CallStatus.FAILED, ContactStatus.FAILED
    else:
        call.status, cstatus = CallStatus.COMPLETED, ContactStatus.COMPLETED
    call.state = CallState.COMPLETED
    if contact:
        contact.status = cstatus
    db.commit()

    bus.publish({
        "type": "call_update", "call_id": call.id, "campaign_id": call.campaign_id,
        "contact_id": call.contact_id, "contact_name": contact.name if contact else "",
        "status": call.status, "state": call.state, "duration": call.duration,
        "feed": True, "ts": datetime.utcnow().isoformat(),
    })
    return {"ok": True, "call_id": call.id}


def _normalize_transcript(raw) -> list[dict]:
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            role = item.get("role", "person")
            role = "ai" if role in ("assistant", "ai", "bot") else "person"
            out.append({"role": role,
                        "text": item.get("content") or item.get("text") or "",
                        "ts": item.get("ts")})
    return out
