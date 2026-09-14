"""Instruction -> extraction schema preview."""
from __future__ import annotations

from fastapi import APIRouter

from ..schemas import SchemaPreviewRequest, SchemaPreviewResponse
from ..services.instruction_compiler import generate_schema

router = APIRouter(prefix="/api/schema", tags=["schema"])


@router.post("/preview", response_model=SchemaPreviewResponse)
async def preview_schema(payload: SchemaPreviewRequest) -> SchemaPreviewResponse:
    schema = await generate_schema(payload.instruction)
    return SchemaPreviewResponse(**schema)
