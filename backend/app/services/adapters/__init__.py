"""Adapter selection based on configuration."""
from __future__ import annotations

from ...config import settings
from .base import CallAdapter
from .mock import MockAdapter
from .bolna import BolnaAdapter

_instance: CallAdapter | None = None


def get_adapter() -> CallAdapter:
    global _instance
    if _instance is None:
        _instance = BolnaAdapter() if not settings.use_mock else MockAdapter()
    return _instance
