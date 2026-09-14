"""CALTHEM backend — FastAPI application entrypoint.

Application layer that sits on top of the Bolna voice-agent platform. Exposes
the Calthem product API: instruction->schema, spreadsheet import, campaigns,
single & bulk calls, live events, results and export.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import (
    schema, imports, campaigns, calls, results, webhooks, events, demo, overview,
    web_call,
)

app = FastAPI(title="CALTHEM API", version="0.1.0",
              description=settings.TAGLINE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    # Allow any Vercel deployment (production + preview URLs) to call the API.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "adapter": settings.TELEPHONY_ADAPTER}


app.include_router(overview.router)
app.include_router(schema.router)
app.include_router(imports.router)
app.include_router(campaigns.router)
app.include_router(calls.router)
app.include_router(results.router)
app.include_router(webhooks.router)
app.include_router(events.router)
app.include_router(demo.router)
app.include_router(web_call.router)
