"""MockAdapter — a fully offline simulated caller.

Drives a realistic call lifecycle (ringing -> connected -> Q&A -> completed)
with believable timing, a generated transcript, and schema-shaped extracted
data. Lets the entire Excel -> queue -> dashboard -> export loop be demoed with
zero telephony credentials. Swappable with BolnaAdapter.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime

from ...db import SessionLocal
from ...models import Call, Contact, CallStatus, CallState, ContactStatus
from ..events import bus
from .base import CallAdapter

# Sample answer pools for common fields (India / college exhibition flavored).
_NAMES = ["Arun Kumar", "Priya Sharma", "Rahul Menon", "Vijay Anand",
          "Sneha Reddy", "Karthik R", "Divya Nair", "Aditya Rao"]
_DEPARTMENTS = ["Computer Science", "AI & Data Science", "Electronics",
                "Mechanical", "Information Technology", "Civil"]
_PROJECTS = ["Smart Attendance System", "AI Crop Advisor", "Traffic Vision",
             "MediTrack", "EcoRoute", "VoiceForm", "CampusConnect"]
_STATUSES = ["Prototype", "In Progress", "Completed", "Planning", "Testing"]
_PROBLEMS = ["Manual attendance tracking", "Crop disease detection is slow",
             "City traffic congestion", "Patient record management",
             "Inefficient delivery routes"]
_GENERIC = ["Yes, that's right", "It's going well", "We're making progress",
            "Quite satisfied overall", "Could be better"]


def _fake_value(field: dict) -> object:
    name = field.get("name", "")
    ftype = field.get("type", "string")
    if ftype == "number":
        if "team" in name or "size" in name or "count" in name:
            return random.randint(2, 6)
        if "rating" in name or "score" in name:
            return random.randint(3, 5)
        if "year" in name or "experience" in name:
            return random.randint(0, 8)
        return random.randint(1, 10)
    if ftype == "boolean":
        return random.choice([True, False])
    if ftype == "list":
        return random.sample(_NAMES, k=random.randint(2, 4))
    # string — choose a themed pool by field name (most specific checks first).
    if "department" in name or "dept" in name or "branch" in name:
        return random.choice(_DEPARTMENTS)
    if "status" in name:
        return random.choice(_STATUSES)
    if "project" in name:  # e.g. project_name, project_title
        return random.choice(_PROJECTS)
    if "problem" in name or "challenge" in name:
        return random.choice(_PROBLEMS)
    # Person-name only when the field is actually about a person's name.
    if name in ("name", "full_name", "student_name", "contact_name", "person") \
            or name.endswith("_name"):
        return random.choice(_NAMES)
    return random.choice(_GENERIC)


def _humanize(value: object) -> str:
    if isinstance(value, bool):
        return "Yes, we do" if value else "No, not really"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


class MockAdapter(CallAdapter):
    name = "mock"

    def __init__(self, speed: float = 1.0) -> None:
        # speed>1 -> faster demo. Base timings kept short for exhibition pacing.
        self.speed = max(speed, 0.1)

    def _sleep(self, seconds: float) -> "asyncio.Future":
        return asyncio.sleep(seconds / self.speed)

    async def run_call(self, call_id: str) -> None:
        db = SessionLocal()
        try:
            call = db.get(Call, call_id)
            if call is None:
                return
            contact = db.get(Contact, call.contact_id)
            campaign = call.campaign
            fields = campaign.extraction_schema.get("fields", []) if campaign else []
            person = (contact.name or "there") if contact else "there"

            started = datetime.utcnow()
            call.started_at = started
            self._set(db, call, CallStatus.CALLING, CallState.PREPARING, contact)

            # --- Ringing ---
            self._set(db, call, CallStatus.RINGING, CallState.RINGING, contact)
            await self._sleep(random.uniform(1.5, 2.5))

            # --- Decide outcome ---
            if contact and not contact.phone_valid:
                return self._finish_unreached(db, call, contact, CallStatus.FAILED,
                                               ContactStatus.INVALID, "Invalid phone number")
            roll = random.random()
            if roll < 0.08:
                await self._sleep(random.uniform(2.0, 3.0))
                return self._finish_unreached(db, call, contact, CallStatus.NO_ANSWER,
                                              ContactStatus.NO_ANSWER, "No answer")
            if roll < 0.12:
                return self._finish_unreached(db, call, contact, CallStatus.BUSY,
                                              ContactStatus.BUSY, "Line busy")

            # --- Connected ---
            self._set(db, call, CallStatus.CONNECTED, CallState.CONNECTED, contact)
            transcript: list[dict] = []
            org = (campaign.organisation or "our team") if campaign else "our team"

            def say(role: str, text: str) -> None:
                transcript.append({
                    "role": role, "text": text,
                    "ts": datetime.utcnow().isoformat(),
                })

            # Intro
            self._set(db, call, CallStatus.IN_PROGRESS, CallState.AI_SPEAKING, contact)
            say("ai", f"Hi{' ' + person if person != 'there' else ''}! I'm Calthem, "
                      f"an AI assistant calling on behalf of {org}. Is now a good "
                      "time for a few quick questions?")
            await self._sleep(1.6)
            self._set(db, call, CallStatus.IN_PROGRESS, CallState.LISTENING, contact)
            say("person", "Yeah, sure, go ahead.")
            await self._sleep(1.0)

            # Q&A per field
            extracted: dict = {}
            for field in fields:
                self._set(db, call, CallStatus.IN_PROGRESS, CallState.AI_SPEAKING, contact)
                say("ai", self._question_for(field))
                await self._sleep(random.uniform(1.2, 1.8))

                self._set(db, call, CallStatus.IN_PROGRESS, CallState.LISTENING, contact)
                value = _fake_value(field)
                extracted[field["name"]] = value
                say("person", _humanize(value))
                await self._sleep(random.uniform(1.0, 1.6))

                self._set(db, call, CallStatus.IN_PROGRESS, CallState.PROCESSING, contact)
                await self._sleep(0.4)

            # Outro
            self._set(db, call, CallStatus.IN_PROGRESS, CallState.AI_SPEAKING, contact)
            say("ai", "That's everything I needed. Thank you so much for your time — "
                      "have a great day!")
            await self._sleep(1.2)

            # --- Complete ---
            ended = datetime.utcnow()
            call.ended_at = ended
            call.duration = round((ended - started).total_seconds(), 1)
            call.transcript = transcript
            call.extracted_data = extracted
            call.recording_url = None  # mock has no recording
            self._set(db, call, CallStatus.COMPLETED, CallState.COMPLETED, contact,
                      contact_status=ContactStatus.COMPLETED)
            db.commit()
            self._publish(call, contact, feed=True)
        except Exception as exc:  # never let one call crash the campaign
            db.rollback()
            try:
                call = db.get(Call, call_id)
                if call:
                    call.status = CallStatus.FAILED
                    call.error = f"mock adapter error: {exc}"
                    contact = db.get(Contact, call.contact_id)
                    if contact:
                        contact.status = ContactStatus.FAILED
                    db.commit()
                    self._publish(call, contact, feed=True)
            except Exception:
                pass
        finally:
            db.close()

    # -- helpers -------------------------------------------------------------
    def _question_for(self, field: dict) -> str:
        label = field.get("label", field.get("name", "that"))
        name = field.get("name", "")
        if "name" in name:
            return "Could you tell me your name, please?"
        if field.get("type") == "boolean":
            return f"And regarding {label.lower()} — could you let me know?"
        if field.get("type") == "number":
            return f"How about {label.lower()} — what's the number?"
        return f"Great. What is your {label.lower()}?"

    def _set(self, db, call: Call, status: str, state: str, contact: Contact | None,
             contact_status: str | None = None) -> None:
        call.status = status
        call.state = state
        if contact is not None:
            if contact_status:
                contact.status = contact_status
            elif status in (CallStatus.CALLING, CallStatus.RINGING, CallStatus.CONNECTED,
                            CallStatus.IN_PROGRESS):
                contact.status = ContactStatus.CALLING
        db.commit()
        self._publish(call, contact)

    def _finish_unreached(self, db, call: Call, contact: Contact | None,
                          call_status: str, contact_status: str, error: str) -> None:
        call.status = call_status
        call.state = CallState.COMPLETED
        call.error = error
        call.ended_at = datetime.utcnow()
        if call.started_at:
            call.duration = round((call.ended_at - call.started_at).total_seconds(), 1)
        if contact is not None:
            contact.status = contact_status
        db.commit()
        self._publish(call, contact, feed=True)

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
