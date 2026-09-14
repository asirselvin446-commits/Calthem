"""Central configuration for the Calthem backend.

All secrets/tunables come from environment variables so nothing sensitive is
hard-coded. See .env.sample for the full list.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Core ---
    APP_NAME: str = "CALTHEM"
    TAGLINE: str = "AI that calls, asks, listens, and collects."
    DB_URL: str = os.getenv("CALTHEM_DB_URL", "sqlite:///./calthem.db")

    # --- Telephony / voice adapter ---
    # "mock"  -> simulated caller (no credentials needed, great for demo)
    # "bolna" -> real Bolna voice-agent + telephony provider
    TELEPHONY_ADAPTER: str = os.getenv("TELEPHONY_ADAPTER", "mock")

    # Bolna engine (native launcher in calthem/bolna_runtime, or Docker).
    # Use 127.0.0.1 (not "localhost") — the engine binds IPv4 and Windows
    # resolves "localhost" to IPv6 ::1 first, which would refuse the connection.
    BOLNA_API_URL: str = os.getenv("BOLNA_API_URL", "http://127.0.0.1:5001")
    # Websocket base the BROWSER uses for web calls (must be browser-reachable).
    BOLNA_WS_URL: str = os.getenv("BOLNA_WS_URL", "ws://127.0.0.1:5001")
    TELEPHONY_API_URL: str = os.getenv("TELEPHONY_API_URL", "http://localhost:8001")

    # Hosted Bolna (https://api.bolna.ai): set BOLNA_API_KEY to switch the adapter
    # from the self-hosted engine to Bolna's managed cloud (it owns the voice
    # engine AND telephony). BOLNA_FROM_NUMBER is a number provisioned in your
    # Bolna account to dial out from. Leave BOLNA_API_KEY empty for self-hosted.
    BOLNA_API_KEY: str = os.getenv("BOLNA_API_KEY", "")
    BOLNA_FROM_NUMBER: str = os.getenv("BOLNA_FROM_NUMBER", "")
    # Base URL where the Bolna engine can POST call results back to Calthem.
    # The engine runs locally, so this is Calthem's own address by default.
    CALTHEM_WEBHOOK_BASE: str = os.getenv("CALTHEM_WEBHOOK_BASE", "http://localhost:8090")

    # --- LLM (instruction -> schema, transcript -> extraction). Optional in mock. ---
    # OpenAI-compatible: leave OPENAI_BASE_URL unset for OpenAI, or point it at a
    # free provider like Groq (https://api.groq.com/openai/v1) with a Groq key.
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL") or None
    SCHEMA_MODEL: str = os.getenv("CALTHEM_SCHEMA_MODEL", "gpt-4o-mini")

    # --- Bulk queue ---
    MAX_CONCURRENCY: int = int(os.getenv("CALTHEM_MAX_CONCURRENCY", "1"))
    MAX_RETRIES: int = int(os.getenv("CALTHEM_MAX_RETRIES", "1"))
    RETRY_DELAY_SECONDS: int = int(os.getenv("CALTHEM_RETRY_DELAY_SECONDS", "8"))

    # --- Regional phone defaults ---
    DEFAULT_REGION: str = os.getenv("CALTHEM_DEFAULT_REGION", "IN")  # India exhibition

    # --- CORS ---
    CORS_ORIGINS: list[str] = os.getenv(
        "CALTHEM_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")

    @property
    def use_mock(self) -> bool:
        return self.TELEPHONY_ADAPTER.lower() == "mock"

    @property
    def bolna_hosted(self) -> bool:
        """True when talking to Bolna's managed cloud (api.bolna.ai) rather than
        the self-hosted engine. Enabled simply by providing an API key."""
        return bool(self.BOLNA_API_KEY.strip())

    def bolna_headers(self) -> dict:
        """Authorization header for hosted Bolna; empty for self-hosted."""
        if self.bolna_hosted:
            return {"Authorization": f"Bearer {self.BOLNA_API_KEY.strip()}"}
        return {}

    def bolna_agent_endpoint(self) -> str:
        """Agent-create endpoint: v2 path on hosted Bolna, /agent self-hosted."""
        base = self.BOLNA_API_URL.rstrip("/")
        return f"{base}/v2/agent" if self.bolna_hosted else f"{base}/agent"

    def bolna_call_endpoint(self) -> str:
        """Outbound-call endpoint."""
        base = self.TELEPHONY_API_URL.rstrip("/")
        return f"{base}/call"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
