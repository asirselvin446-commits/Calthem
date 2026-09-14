"""Server-Sent Events stream for live dashboard updates."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..services.events import bus

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    queue = bus.subscribe()

    async def event_gen():
        try:
            # Initial comment to open the stream promptly.
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # keep proxies from closing the stream
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )
