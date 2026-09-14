"""Calthem's Bolna engine launcher — native, no Docker, no Redis.

This is a thin FastAPI server that hosts the Bolna voice engine for Calthem.
It mirrors Bolna's example `local_setup/quickstart_server.py` but:
  * stores agents in an in-memory dict (the bolna package itself needs no Redis),
  * points pydub at the bundled ffmpeg (imageio-ffmpeg),
  * serves the same POST /agent + WS /chat/v1/{agent_id} contract that both the
    browser web-call and the telephony servers connect to.

Run it with Bolna's own virtualenv (which has `bolna` installed):

    cd calthem/bolna_runtime
    ../../bolna/.venv/Scripts/python.exe server.py         # Windows
    # serves on http://localhost:5001

Requires provider keys in the environment (or a .env file here): OPENAI_API_KEY,
DEEPGRAM_AUTH_TOKEN, ELEVENLABS_API_KEY, and EXTRACTION_PROMPT_GENERATION_MODEL.
"""
from __future__ import annotations

import os
import json
import uuid
import asyncio
import traceback

# --- make pydub find ffmpeg (bundled via imageio-ffmpeg) BEFORE bolna imports ---
try:
    import imageio_ffmpeg
    from pydub import AudioSegment

    _ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    AudioSegment.converter = _ffmpeg
    os.environ["PATH"] = os.path.dirname(_ffmpeg) + os.pathsep + os.environ.get("PATH", "")
except Exception as _e:  # pragma: no cover
    print(f"[warn] ffmpeg setup skipped: {_e}")

# Run from this file's directory so bolna's agent_data/ (relative PREPROCESS_DIR)
# is consistent between agent creation and the websocket session.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List

from bolna.helpers.utils import store_file
from bolna.prompts import EXTRACTION_PROMPT_GENERATION_PROMPT
from bolna.helpers.logger_config import configure_logger
from bolna.models import AgentModel
from bolna.llms import LiteLLM
from bolna.agent_manager.assistant_manager import AssistantManager

logger = configure_logger(__name__)

# In-memory agent store (single process; fine for local/demo use).
AGENTS: Dict[str, dict] = {}

app = FastAPI(title="Calthem Bolna Engine")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


class CreateAgentPayload(BaseModel):
    agent_config: AgentModel
    agent_prompts: Optional[Dict[str, Dict[str, str]]] = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "engine": "bolna", "agents": len(AGENTS)}


@app.post("/agent")
async def create_agent(payload: CreateAgentPayload) -> dict:
    agent_uuid = str(uuid.uuid4())
    data_for_db = payload.agent_config.model_dump()
    data_for_db["assistant_status"] = "seeding"
    agent_prompts = payload.agent_prompts or {}

    # Auto-generate the extraction schema from the natural-language instruction,
    # exactly like Bolna's reference server does.
    for index, task in enumerate(data_for_db.get("tasks", [])):
        if task.get("task_type") == "extraction":
            model = os.getenv("EXTRACTION_PROMPT_GENERATION_MODEL", "gpt-4o-mini")
            try:
                gen = LiteLLM(model=model, max_tokens=2000)
                details = task["tools_config"]["llm_agent"].get("extraction_details", "")
                extraction_prompt = await gen.generate(messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT_GENERATION_PROMPT},
                    {"role": "user", "content": details},
                ])
                data_for_db["tasks"][index]["tools_config"]["llm_agent"]["extraction_json"] = extraction_prompt
            except Exception as e:
                logger.error(f"extraction schema generation failed: {e}")

    AGENTS[agent_uuid] = data_for_db
    await store_file(file_key=f"{agent_uuid}/conversation_details.json",
                     file_data=agent_prompts, local=True)
    return {"agent_id": agent_uuid, "state": "created"}


@app.get("/agent/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AGENTS[agent_id]


@app.websocket("/chat/v1/{agent_id}")
async def websocket_endpoint(agent_id: str, websocket: WebSocket, user_agent: str = Query(None)):
    await websocket.accept()
    agent_config = AGENTS.get(agent_id)
    if agent_config is None:
        await websocket.close(code=4404)
        return

    assistant_manager = AssistantManager(agent_config, websocket, agent_id)
    try:
        async for index, task_output in assistant_manager.run(local=True):
            logger.info(f"task {index} output ready")
    except WebSocketDisconnect:
        logger.info("web client disconnected")
    except Exception as e:
        traceback.print_exc()
        logger.error(f"error running assistant: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("BOLNA_PORT", "5001")))
