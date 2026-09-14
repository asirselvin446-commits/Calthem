"""BolnaAdapter — real voice calls via the Bolna orchestration platform.

Flow:
  1. Ensure a Bolna agent exists for the campaign (POST {BOLNA_API_URL}/agent),
     compiled from the campaign instruction with a webhook task that posts the
     extracted data back to Calthem.
  2. Trigger an outbound call (POST {TELEPHONY_API_URL}/call).
  3. The call runs asynchronously; completion + extracted_data arrive later at
     Calthem's /api/webhooks/bolna endpoint (see routers/webhooks.py), which
     finalizes the Call row.

This adapter therefore only *starts* the call and marks it CALLING. It is the
real counterpart to MockAdapter and is selected when TELEPHONY_ADAPTER=bolna.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from ...config import settings
from ...db import SessionLocal
from ...models import Call, Contact, Campaign, CallStatus, CallState, ContactStatus
from ..events import bus
from ..instruction_compiler import build_agent_config
from .base import CallAdapter


class BolnaAdapter(CallAdapter):
    name = "bolna"

    async def ensure_agent(self, campaign: Campaign, db) -> str:
        """Create the Bolna agent for this campaign if not already created."""
        if campaign.agent_id:
            return campaign.agent_id

        webhook_url = f"{settings.CALTHEM_WEBHOOK_BASE.rstrip('/')}/api/webhooks/bolna"
        config = campaign.agent_config or build_agent_config(
            name=campaign.name,
            instruction=campaign.instruction,
            schema=campaign.extraction_schema,
            organisation=campaign.organisation,
            voice=campaign.voice,
            language=campaign.language,
            max_duration=campaign.max_duration,
            webhook_url=webhook_url,
            webhook_in_config=settings.bolna_hosted,
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.bolna_agent_endpoint(), json=config, headers=settings.bolna_headers()
            )
            resp.raise_for_status()
            agent_id = resp.json().get("agent_id")
        campaign.agent_id = agent_id
        db.commit()
        return agent_id

    async def run_call(self, call_id: str) -> None:
        db = SessionLocal()
        try:
            call = db.get(Call, call_id)
            if call is None:
                return
            contact = db.get(Contact, call.contact_id)
            campaign = call.campaign

            if contact and not contact.phone_valid:
                call.status = CallStatus.FAILED
                call.error = "Invalid phone number"
                call.ended_at = datetime.utcnow()
                if contact:
                    contact.status = ContactStatus.INVALID
                db.commit()
                self._publish(call, contact, feed=True)
                return

            agent_id = await self.ensure_agent(campaign, db)

            call.status = CallStatus.CALLING
            call.state = CallState.PREPARING
            call.started_at = datetime.utcnow()
            if contact:
                contact.status = ContactStatus.CALLING
                contact.attempts += 1
            db.commit()
            self._publish(call, contact)

            # Pass call_id so the webhook can correlate the result back to this row.
            payload = {
                "agent_id": agent_id,
                "recipient_phone_number": call.phone,
                "user_data": {"calthem_call_id": call.id, "recipient_name": contact.name if contact else ""},
            }
            # Hosted Bolna requires the caller ID (a number provisioned in the
            # Bolna account) to place the outbound call.
            if settings.bolna_hosted and settings.BOLNA_FROM_NUMBER.strip():
                payload["from_phone_number"] = settings.BOLNA_FROM_NUMBER.strip()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    settings.bolna_call_endpoint(), json=payload, headers=settings.bolna_headers()
                )
                resp.raise_for_status()
                # Hosted Bolna returns an execution_id for tracking; keep it for
                # correlation and result polling.
                try:
                    execution_id = resp.json().get("execution_id")
                    if execution_id:
                        call.provider_call_id = execution_id
                except Exception:
                    pass

            call.status = CallStatus.RINGING
            call.state = CallState.RINGING
            db.commit()
            self._publish(call, contact)
            # Completion is handled asynchronously by the webhook receiver.
        except Exception as exc:
            db.rollback()
            call = db.get(Call, call_id)
            if call:
                call.status = CallStatus.FAILED
                call.error = f"bolna adapter error: {exc}"
                contact = db.get(Contact, call.contact_id)
                if contact:
                    contact.status = ContactStatus.FAILED
                db.commit()
                self._publish(call, contact, feed=True)
        finally:
            db.close()

    def _publish(self, call: Call, contact: Contact | None, feed: bool = False) -> None:
        bus.publish({
            "type": "call_update",
            "call_id": call.id,
            "campaign_id": call.campaign_id,
            "contact_id": call.contact_id,
            "contact_name": contact.name if contact else "",
            "status": call.status,
            "state": call.state,
            "duration": call.duration,
            "feed": feed,
            "ts": datetime.utcnow().isoformat(),
        })
