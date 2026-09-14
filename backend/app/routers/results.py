"""Results table (dynamic columns) and export to Excel / CSV / JSON."""
from __future__ import annotations

import io
import json
import re

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Campaign, Contact, Call, CallStatus

router = APIRouter(prefix="/api/campaigns", tags=["results"])


def _norm_key(k: object) -> str:
    """Normalize a field key for tolerant matching (lowercase, alphanumeric only)."""
    return re.sub(r"[^a-z0-9]", "", str(k).lower())


def _build_rows(db: Session, campaign: Campaign) -> tuple[list[dict], list[dict]]:
    """Return (columns, rows). Columns = fixed contact cols + dynamic schema cols."""
    fields = campaign.extraction_schema.get("fields", [])
    columns = [
        {"name": "name", "label": "Name"},
        {"name": "phone", "label": "Phone"},
    ]
    seen = {"name", "phone"}
    for f in fields:
        if f["name"] not in seen:
            columns.append({"name": f["name"], "label": f.get("label", f["name"])})
            seen.add(f["name"])
    columns.append({"name": "status", "label": "Status"})
    columns.append({"name": "collected_at", "label": "Collected At"})

    contacts = db.query(Contact).filter(Contact.campaign_id == campaign.id).all()
    rows: list[dict] = []
    for contact in contacts:
        # Latest completed call wins; else latest attempt.
        calls = sorted(contact.calls, key=lambda c: c.created_at)
        completed = [c for c in calls if c.status == CallStatus.COMPLETED]
        latest = completed[-1] if completed else (calls[-1] if calls else None)

        row: dict = {
            "contact_id": contact.id,
            "call_id": latest.id if latest else None,
            "name": contact.name,
            "phone": contact.phone,
            "status": latest.status if latest else contact.status,
            "collected_at": latest.ended_at.isoformat() if latest and latest.ended_at else None,
        }
        extracted = (latest.extracted_data if latest else {}) or {}
        # Bolna picks its own key names from the instruction, which may differ in
        # case/spacing/underscores from Calthem's field names. Match tolerantly.
        norm_extracted = {_norm_key(k): v for k, v in extracted.items()}
        for f in fields:
            val = extracted.get(f["name"])
            if val is None:
                val = norm_extracted.get(_norm_key(f["name"]))
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            row[f["name"]] = val if val is not None else (contact.extra.get(f["name"]) if contact.extra else None)
        # Fill name/phone from extraction if contact lacked them (single-call mode).
        if not row["name"] and extracted.get("name"):
            row["name"] = extracted["name"]
        rows.append(row)
    return columns, rows


@router.get("/{campaign_id}/results")
def get_results(campaign_id: str, db: Session = Depends(get_db),
                search: str = Query("", description="filter across all fields"),
                status: str = Query("", description="filter by status")) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    columns, rows = _build_rows(db, campaign)

    if status:
        rows = [r for r in rows if r.get("status") == status]
    if search:
        s = search.lower()
        rows = [r for r in rows
                if any(s in str(v).lower() for v in r.values() if v is not None)]

    return {"campaign": campaign.name, "columns": columns, "rows": rows}


@router.get("/{campaign_id}/export")
def export_results(campaign_id: str, format: str = Query("xlsx"),
                   db: Session = Depends(get_db)) -> StreamingResponse:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    columns, rows = _build_rows(db, campaign)

    col_names = [c["name"] for c in columns]
    labels = {c["name"]: c["label"] for c in columns}
    table = [{labels[cn]: r.get(cn) for cn in col_names} for r in rows]

    safe = "".join(ch for ch in campaign.name if ch.isalnum() or ch in " -_").strip() or "calthem"

    if format == "json":
        payload = json.dumps({"campaign": campaign.name, "rows": table}, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(payload.encode()), media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe}.json"'})

    df = pd.DataFrame(table)
    if format == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{safe}.csv"'})

    # default xlsx
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}.xlsx"'})
