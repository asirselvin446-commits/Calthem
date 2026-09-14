# CALTHEM

**AI that calls, asks, listens, and collects.**
Turn phone conversations into structured data.

Calthem is an autonomous AI voice information-collection platform built as an
application layer on top of the open-source [Bolna](https://github.com/bolna-ai/bolna)
voice-agent platform (vendored in `../bolna`).

You give Calthem a phone number **or** a spreadsheet of contacts, plus a plain
instruction ("*ask their name, department, project and team size*"). Calthem
derives the questions, calls each person, holds a natural conversation, extracts
structured JSON, and shows it on a dashboard you can export to Excel/CSV/JSON.

---

## Architecture

```
Next.js dashboard  ──HTTP/SSE──►  Calthem FastAPI backend  ──►  Call adapter
  (monochrome glass UI)             (campaigns, contacts,        ├─ MockAdapter  (simulated, default)
                                     calls, extraction,          └─ BolnaAdapter (real: Bolna + Twilio/Plivo)
                                     results, export)                    │
                                            │                            ▼
                                        SQLite DB                Bolna voice platform → phone call
                                                                         │ (webhook posts extracted data back)
                                                                         ▼
                                                                 Calthem result ingest
```

The **adapter interface** (`app/services/adapters/`) makes the caller
swappable: `mock` needs no credentials and simulates the whole call lifecycle;
`bolna` places real calls and receives results via webhook. Everything else —
dynamic schema generation, the queue, results, export — is identical in both.

## Backend (FastAPI + SQLite)

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.sample .env               # defaults to mock mode — no keys needed
uvicorn app.main:app --port 8090
```

Key env vars (see `backend/.env.sample`):

| Var | Purpose |
|-----|---------|
| `TELEPHONY_ADAPTER` | `mock` (default) or `bolna` |
| `OPENAI_API_KEY` | optional — enables LLM schema generation (offline heuristic otherwise) |
| `CALTHEM_MAX_CONCURRENCY` | bulk-call concurrency (1 for the demo) |
| `BOLNA_API_URL`, `TELEPHONY_API_URL`, `CALTHEM_WEBHOOK_BASE` | only for `bolna` mode |

## Frontend (Next.js + Tailwind)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000  (expects backend at :8090)
```

## Exhibition Demo Mode

1. Open the dashboard → **Run Demo** (or `POST /api/demo/seed`).
2. A "Student Project Survey" campaign is seeded with sample students.
3. **Start Calling** → watch the live activity feed and progress.
4. Open any completed call for its transcript + structured extraction.
5. **Results** tab → export **XLSX / CSV / JSON**.

No telephony credentials are required in mock mode — every call is simulated.

## Going live with real calls

1. Run Bolna + a telephony provider (Twilio/Plivo) + ngrok (see `../bolna/local_setup`).
2. Set `TELEPHONY_ADAPTER=bolna` and the Bolna/telephony URLs in `backend/.env`.
3. Ensure `CALTHEM_WEBHOOK_BASE` is a public URL Bolna can POST results to.
4. Restart the backend. The dashboard and workflow are unchanged.

## API surface (selected)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/schema/preview` | instruction → extraction fields |
| POST | `/api/import` | parse .xlsx/.xls/.csv → contacts |
| POST | `/api/campaigns` | create a campaign (compiles schema + agent config) |
| POST | `/api/campaigns/{id}/start` | run the bulk queue |
| POST | `/api/calls/single` | Mode A — one call now |
| GET  | `/api/calls/{id}` | live call state + transcript + extraction |
| GET  | `/api/campaigns/{id}/results` | dynamic results table |
| GET  | `/api/campaigns/{id}/export?format=xlsx\|csv\|json` | export |
| GET  | `/api/events/stream` | Server-Sent Events for the live dashboard |
| POST | `/api/webhooks/bolna` | ingest real call results (bolna mode) |

## Responsible use

Calls identify themselves as an AI assistant. Only call people who have agreed
to receive calls. Secrets live in environment variables, never in the frontend.
