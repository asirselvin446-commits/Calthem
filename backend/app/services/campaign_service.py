"""Campaign creation helpers: compile instruction -> schema + agent config,
persist campaign + contacts, and compute live stats.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Campaign, Contact, Call, CampaignStatus, ContactStatus, CallStatus
from .instruction_compiler import generate_schema, build_agent_config
from .phone import normalize_phone


async def create_campaign(
    db: Session,
    *,
    name: str | None,
    mode: str,
    instruction: str,
    organisation: str = "",
    voice: str = "default",
    language: str = "en",
    max_duration: int = 180,
    concurrency: int = 1,
    max_retries: int = 1,
    contacts: list[dict] | None = None,
) -> Campaign:
    schema = await generate_schema(instruction)
    webhook_url = f"{settings.CALTHEM_WEBHOOK_BASE.rstrip('/')}/api/webhooks/bolna"
    resolved_name = name or _derive_name(instruction)
    agent_config = build_agent_config(
        name=resolved_name,
        instruction=instruction,
        schema=schema,
        organisation=organisation,
        voice=voice,
        language=language,
        max_duration=max_duration,
        webhook_url=webhook_url,
        # Hosted Bolna needs webhook_url INSIDE agent_config (not as a task),
        # otherwise call results are never posted back to Calthem.
        webhook_in_config=settings.bolna_hosted,
    )

    campaign = Campaign(
        name=resolved_name,
        mode=mode,
        instruction=instruction,
        extraction_schema=schema,
        agent_config=agent_config,
        organisation=organisation,
        voice=voice,
        language=language,
        max_duration=max_duration,
        concurrency=concurrency,
        max_retries=max_retries,
        status=CampaignStatus.READY,
    )
    db.add(campaign)
    db.flush()  # assign id

    for c in contacts or []:
        phone, valid = normalize_phone(c.get("phone", ""), language_region(language))
        db.add(Contact(
            campaign_id=campaign.id,
            name=c.get("name", "") or "",
            phone=phone or c.get("phone", ""),
            phone_valid=valid,
            email=c.get("email"),
            department=c.get("department"),
            extra=c.get("extra", {}) or {},
            status=ContactStatus.PENDING if valid else ContactStatus.INVALID,
        ))

    db.commit()
    db.refresh(campaign)
    return campaign


def language_region(language: str) -> str:
    # Simple mapping; extend as needed. Defaults to configured region.
    return settings.DEFAULT_REGION


def _derive_name(instruction: str) -> str:
    words = instruction.strip().split()
    snippet = " ".join(words[:6])
    return (snippet[:48] + "…") if len(snippet) > 48 else (snippet or "New Campaign")


def compute_stats(db: Session, campaign_id: str) -> dict:
    contacts = db.query(Contact).filter(Contact.campaign_id == campaign_id).all()
    counts = {
        "total": len(contacts),
        "pending": 0, "calling": 0, "completed": 0,
        "failed": 0, "no_answer": 0, "busy": 0,
    }
    for c in contacts:
        key = {
            ContactStatus.PENDING: "pending",
            ContactStatus.CALLING: "calling",
            ContactStatus.COMPLETED: "completed",
            ContactStatus.FAILED: "failed",
            ContactStatus.NO_ANSWER: "no_answer",
            ContactStatus.BUSY: "busy",
            ContactStatus.INVALID: "failed",
        }.get(c.status)
        if key:
            counts[key] += 1
    return counts
