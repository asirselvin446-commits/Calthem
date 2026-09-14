"""Exhibition Demo Mode — one call seeds a ready-to-run demo campaign."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import CampaignOut
from ..services.campaign_service import create_campaign

router = APIRouter(prefix="/api/demo", tags=["demo"])

_DEMO_INSTRUCTION = (
    "Call each student and collect their name, department, project name, "
    "team size and current project status."
)

_DEMO_CONTACTS = [
    {"name": "Arun Kumar", "phone": "+919000000001", "department": "CSE"},
    {"name": "Priya Sharma", "phone": "+919000000002", "department": "AIDS"},
    {"name": "Rahul Menon", "phone": "+919000000003", "department": "ECE"},
    {"name": "Sneha Reddy", "phone": "+919000000004", "department": "IT"},
    {"name": "Vijay Anand", "phone": "+919000000005", "department": "MECH"},
    {"name": "Divya Nair", "phone": "+919000000006", "department": "CSE"},
]


@router.post("/seed", response_model=CampaignOut)
async def seed_demo(db: Session = Depends(get_db)):
    """Create a fresh demo campaign with sample students, ready to Start."""
    campaign = await create_campaign(
        db,
        name="Student Project Survey (Demo)",
        mode="bulk",
        instruction=_DEMO_INSTRUCTION,
        organisation="Calthem College Expo",
        concurrency=1,
        max_retries=1,
        contacts=_DEMO_CONTACTS,
    )
    return campaign
