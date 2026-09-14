"""Telephony/voice adapter interface.

An adapter is responsible for actually placing a call for a given Call row and
driving it to completion: updating status/state, transcript, extracted_data,
duration, and publishing live events. The rest of Calthem is adapter-agnostic,
so the MockAdapter (demo) and BolnaAdapter (real) are fully interchangeable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class CallAdapter(ABC):
    name: str = "base"

    @abstractmethod
    async def run_call(self, call_id: str) -> None:
        """Place and complete a single call, persisting all results to the DB."""
        raise NotImplementedError
