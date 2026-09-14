"""Pydantic request/response models for the Calthem API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# --- Instruction / schema ---
class SchemaPreviewRequest(BaseModel):
    instruction: str


class Field(BaseModel):
    name: str
    label: str
    type: str = "string"
    required: bool = True
    description: str = ""


class SchemaPreviewResponse(BaseModel):
    fields: list[Field]


# --- Contacts ---
class ContactIn(BaseModel):
    name: str = ""
    phone: str
    email: Optional[str] = None
    department: Optional[str] = None
    extra: dict[str, Any] = {}


class ContactOut(BaseModel):
    id: str
    name: str
    phone: str
    phone_valid: bool
    email: Optional[str] = None
    department: Optional[str] = None
    extra: dict[str, Any] = {}
    status: str
    attempts: int

    class Config:
        from_attributes = True


# --- Campaigns ---
class CampaignCreate(BaseModel):
    name: Optional[str] = None
    mode: str = "bulk"  # "single" | "bulk"
    instruction: str
    organisation: str = ""
    voice: str = "default"
    language: str = "en"
    max_duration: int = 180
    concurrency: int = 1
    max_retries: int = 1
    contacts: list[ContactIn] = []


class CampaignOut(BaseModel):
    id: str
    name: str
    mode: str
    instruction: str
    extraction_schema: dict[str, Any]
    organisation: str
    voice: str
    language: str
    max_duration: int
    concurrency: int
    max_retries: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    total: int
    pending: int
    calling: int
    completed: int
    failed: int
    no_answer: int
    busy: int


class CampaignDetail(CampaignOut):
    stats: CampaignStats
    contact_count: int


# --- Calls ---
class CallOut(BaseModel):
    id: str
    campaign_id: str
    contact_id: str
    phone: str
    status: str
    state: str
    duration: float
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    recording_url: Optional[str] = None
    extracted_data: dict[str, Any] = {}
    error: Optional[str] = None

    class Config:
        from_attributes = True


class CallDetail(CallOut):
    transcript: list[dict[str, Any]] = []
    contact_name: str = ""


# --- Single call quick-start ---
class SingleCallRequest(BaseModel):
    phone: str
    instruction: str
    name: str = ""
    organisation: str = ""
    voice: str = "default"
    language: str = "en"
    max_duration: int = 180
