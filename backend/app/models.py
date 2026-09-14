"""SQLAlchemy ORM models for Calthem.

Data model (per the product brief):
  Campaign 1---* Contact
  Campaign 1---* Call
  Contact  1---* Call   (a contact can have multiple call attempts)

The compiled Bolna agent config and the dynamically-generated extraction
schema both live on the Campaign, so every call in a campaign shares them.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, Text, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Status vocabularies (kept as plain strings for portability / easy JSON)
# ---------------------------------------------------------------------------
class CampaignStatus:
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ContactStatus:
    PENDING = "pending"
    CALLING = "calling"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    INVALID = "invalid"


class CallStatus:
    PREPARING = "preparing"
    CALLING = "calling"
    RINGING = "ringing"
    CONNECTED = "connected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"


# Live conversational sub-states surfaced on the dashboard during a call.
class CallState:
    PREPARING = "preparing"
    RINGING = "ringing"
    CONNECTED = "connected"
    AI_SPEAKING = "ai_speaking"
    LISTENING = "listening"
    PROCESSING = "processing"
    COMPLETED = "completed"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="Untitled Campaign")
    mode: Mapped[str] = mapped_column(String(16), default="bulk")  # "single" | "bulk"
    instruction: Mapped[str] = mapped_column(Text, default="")

    # Dynamically generated from the instruction.
    extraction_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    # Compiled Bolna agent config (used by the BolnaAdapter); stored for reuse.
    agent_config: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Presentation / voice options
    organisation: Mapped[str] = mapped_column(String(255), default="")
    voice: Mapped[str] = mapped_column(String(64), default="default")
    language: Mapped[str] = mapped_column(String(16), default="en")
    max_duration: Mapped[int] = mapped_column(Integer, default=180)  # seconds

    # Queue controls
    concurrency: Mapped[int] = mapped_column(Integer, default=1)
    max_retries: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[str] = mapped_column(String(16), default=CampaignStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    calls: Mapped[list["Call"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)

    name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    phone_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Any additional spreadsheet columns preserved as-is.
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(16), default=ContactStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    campaign: Mapped["Campaign"] = relationship(back_populates="contacts")
    calls: Mapped[list["Call"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"), index=True)

    phone: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(16), default=CallStatus.PREPARING)
    state: Mapped[str] = mapped_column(String(16), default=CallState.PREPARING)

    # External identifiers (Bolna run_id / telephony call_sid) for correlation.
    provider_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0)  # seconds

    transcript: Mapped[list] = mapped_column(JSON, default=list)  # [{role, text, ts}]
    recording_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    campaign: Mapped["Campaign"] = relationship(back_populates="calls")
    contact: Mapped["Contact"] = relationship(back_populates="calls")
