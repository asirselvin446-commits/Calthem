"""Spreadsheet upload -> parsed contact preview (no persistence yet)."""
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException

from ..services.excel_import import parse_contacts

router = APIRouter(prefix="/api/import", tags=["import"])

_ALLOWED = (".xlsx", ".xls", ".csv", ".xlsm")
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("")
async def import_file(file: UploadFile = File(...)) -> dict:
    filename = (file.filename or "").lower()
    if not filename.endswith(_ALLOWED):
        raise HTTPException(status_code=400,
                            detail="Unsupported file type. Upload .xlsx, .xls or .csv")
    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB).")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    try:
        result = parse_contacts(file.filename, content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")
    return {"filename": file.filename, **result}
