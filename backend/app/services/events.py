"""In-process pub/sub event bus for live dashboard updates.

Adapters and the queue publish events (call state changes, activity-feed
entries); the API's SSE endpoint subscribes and streams them to the frontend.
Simple asyncio.Queue fan-out — sufficient for a single-process demo/prototype.
"""
from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop for a slow consumer rather than blocking the caller.
                pass


bus = EventBus()
