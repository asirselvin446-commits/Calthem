"""Instruction -> extraction schema + Bolna agent config.

This is the intelligence that turns a free-form instruction like
    "Ask their name, department, project name, team size and current status"
into:
  1. a structured extraction schema (dynamic fields),
  2. a natural conversational system prompt,
  3. a Bolna-compatible multi-task agent config.

When OPENAI_API_KEY is set, an LLM generates the schema. Otherwise a robust
offline heuristic parses the instruction so the whole product still works in
demo/mock mode with zero credentials.
"""
from __future__ import annotations

import json
import re

from ..config import settings

# Words that commonly introduce the list of things to collect.
_TRIGGERS = [
    "collect", "ask", "find out", "gather", "know", "about their",
    "their", "record", "capture", "get their",
]

# Map keywords -> (canonical field name, type) to type-infer heuristic fields.
_TYPE_HINTS = {
    "number": ["size", "count", "number of", "how many", "rating", "years",
               "age", "score", "team size", "quantity", "amount"],
    "boolean": ["whether", "need help", "needs help", "would recommend",
                "interested", "agree", "yes or no", "do they", "are they"],
    "list": ["members", "team members", "names of", "list of", "features"],
}

_STOPWORDS = {
    "the", "their", "them", "a", "an", "and", "or", "of", "for", "to", "please",
    "call", "each", "every", "person", "people", "student", "students", "customer",
    "customers", "applicant", "applicants", "ask", "collect", "find", "out",
    "about", "whether", "they", "his", "her", "this", "these", "those",
}


def _infer_type(text: str) -> str:
    t = text.lower()
    for typ, keys in _TYPE_HINTS.items():
        if any(k in t for k in keys):
            return typ
    return "string"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "field"


def _label(text: str) -> str:
    words = [w for w in re.split(r"[\s_]+", text.strip()) if w]
    return " ".join(w.capitalize() for w in words) if words else "Field"


def heuristic_schema(instruction: str) -> dict:
    """Parse an instruction into fields without any LLM. Best-effort but solid."""
    text = instruction.strip()
    lowered = text.lower()

    # Find the segment after the last trigger word, which usually holds the list.
    segment = text
    best_idx = -1
    for trig in _TRIGGERS:
        idx = lowered.rfind(trig)
        if idx > best_idx:
            best_idx = idx
            segment = text[idx + len(trig):]

    # Normalize separators: split on commas, semicolons, newlines, bullets, " and ".
    segment = re.sub(r"\band\b", ",", segment, flags=re.IGNORECASE)
    segment = re.sub(r"[\n;•\-\*]+", ",", segment)
    parts = [p.strip(" .:\t") for p in segment.split(",")]

    fields: list[dict] = []
    seen: set[str] = set()
    for part in parts:
        # Trim filler words at the edges.
        cleaned = re.sub(r"^(their|the|a|an|any)\s+", "", part, flags=re.IGNORECASE).strip()
        # Drop overly long or empty fragments (likely not a field).
        words = [w for w in re.split(r"\s+", cleaned) if w]
        content_words = [w for w in words if w.lower() not in _STOPWORDS]
        if not content_words or len(words) > 8:
            continue
        name = _slugify(cleaned)
        if not name or name in seen:
            continue
        seen.add(name)
        fields.append({
            "name": name,
            "label": _label(cleaned),
            "type": _infer_type(cleaned),
            "required": True,
            "description": f"The {_label(cleaned).lower()} of the person.",
        })

    # Always guarantee at least a name field so results tables are meaningful.
    if not any(f["name"] in ("name", "full_name") for f in fields):
        fields.insert(0, {
            "name": "name", "label": "Name", "type": "string",
            "required": True, "description": "The person's full name.",
        })

    return {"fields": fields}


async def llm_schema(instruction: str) -> dict | None:
    """Generate a schema via OpenAI. Returns None on any failure (caller falls back)."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI  # lazy import

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
        system = (
            "You convert a data-collection instruction into a JSON extraction "
            "schema. Output ONLY JSON of the form "
            '{\"fields\":[{\"name\":\"snake_case\",\"label\":\"Human Label\",'
            '\"type\":\"string|number|boolean|list\",\"required\":true,'
            '\"description\":\"what to collect\"}]}. '
            "Infer sensible field names, types and order. Keep 2-10 fields."
        )
        resp = await client.chat.completions.create(
            model=settings.SCHEMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": instruction},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content)
        if isinstance(data, dict) and isinstance(data.get("fields"), list) and data["fields"]:
            # Normalize/repair each field.
            for f in data["fields"]:
                f["name"] = _slugify(str(f.get("name", "field")))
                f.setdefault("label", _label(f["name"]))
                f.setdefault("type", "string")
                f.setdefault("required", True)
                f.setdefault("description", "")
            return {"fields": data["fields"]}
    except Exception:
        return None
    return None


async def generate_schema(instruction: str) -> dict:
    """Public entry: LLM schema if available, else heuristic. Never raises."""
    schema = await llm_schema(instruction)
    if schema:
        return schema
    return heuristic_schema(instruction)


async def extract_from_transcript(instruction: str, schema: dict, transcript_text: str) -> dict | None:
    """Extract the schema fields from a call transcript using the LLM.

    Used when the telephony provider returns a transcript but no structured
    extraction (e.g. hosted Bolna without a configured extraction). Returns a
    {field_name: value} dict, or None if no OPENAI_API_KEY / on any failure.
    """
    if not settings.OPENAI_API_KEY or not transcript_text:
        return None
    fields = schema.get("fields", [])
    if not fields:
        return None
    try:
        from openai import AsyncOpenAI  # lazy import

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
        field_lines = "\n".join(
            f'- "{f["name"]}" ({f.get("type", "string")}): {f.get("label", f["name"])}'
            for f in fields
        )
        system = (
            "You extract structured data from a phone-call transcript. "
            "Return ONLY a JSON object whose keys are EXACTLY the field names below "
            "and whose values are what the person said (use null if not stated). "
            "Numbers as numbers, lists as arrays.\nFields:\n" + field_lines
        )
        resp = await client.chat.completions.create(
            model=settings.SCHEMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Instruction: {instruction}\n\nTranscript:\n{transcript_text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(resp.choices[0].message.content)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def build_conversation_prompt(instruction: str, schema: dict, organisation: str = "") -> str:
    """Compose the system prompt the voice agent follows during the call."""
    org = organisation.strip() or "our organisation"
    field_lines = "\n".join(
        f"  - {f['label']} ({f['type']})" for f in schema.get("fields", [])
    )
    return (
        f"You are Calthem, a polite AI voice assistant calling on behalf of {org}.\n"
        "You are speaking on a phone call. Follow these rules strictly:\n"
        "1. Clearly introduce yourself as an AI assistant at the start.\n"
        "2. Ask for permission to proceed with a few quick questions.\n"
        "3. Ask ONE question at a time and wait for the answer.\n"
        "4. Speak naturally and conversationally; keep turns short.\n"
        "5. Ask a brief follow-up only if an answer is unclear.\n"
        "6. Do not repeat questions that are already answered.\n"
        "7. When you have everything, thank them warmly and end the call.\n\n"
        f"Your goal for this call is to collect the following information:\n{field_lines}\n\n"
        f"Original instruction from the operator: \"{instruction.strip()}\"\n"
    )


def build_agent_config(
    *,
    name: str,
    instruction: str,
    schema: dict,
    organisation: str = "",
    voice: str = "default",
    language: str = "en",
    max_duration: int = 180,
    webhook_url: str | None = None,
    webhook_in_config: bool = False,
) -> dict:
    """Build a Bolna multi-task agent config: conversation -> extraction -> webhook.

    Mirrors the structure Bolna's quickstart_server expects. `extraction_details`
    is the natural-language instruction; Bolna auto-generates the extraction JSON
    from it at agent-create time.

    `webhook_in_config`: hosted Bolna (api.bolna.ai) expects the webhook as an
    `agent_config.webhook_url` field rather than a webhook *task*. Set True for
    hosted; leave False for the self-hosted engine (which uses the task form).
    """
    system_prompt = build_conversation_prompt(instruction, schema, organisation)

    tasks: list[dict] = [
        {
            "task_type": "conversation",
            "toolchain": {
                "execution": "parallel",
                "pipelines": [["transcriber", "llm", "synthesizer"]],
            },
            "tools_config": {
                "input": {"format": "wav", "provider": settings.BOLNA_TELEPHONY_PROVIDER},
                "output": {"format": "wav", "provider": settings.BOLNA_TELEPHONY_PROVIDER},
                "transcriber": {
                    "encoding": "linear16",
                    "language": settings.BOLNA_STT_LANGUAGE or language,
                    "model": settings.BOLNA_STT_MODEL,
                    "provider": settings.BOLNA_STT_PROVIDER,
                    "stream": True,
                },
                "llm_agent": {
                    "agent_type": "simple_llm_agent",
                    "agent_flow_type": "streaming",
                    "llm_config": {
                        "provider": "openai",
                        "model": settings.BOLNA_LLM_MODEL,
                        "request_json": False,
                    },
                },
                "synthesizer": {
                    "audio_format": "wav",
                    "provider": "elevenlabs",
                    "stream": True,
                    "provider_config": {
                        "voice": "George",
                        "model": "eleven_turbo_v2_5",
                        "voice_id": "JBFqnCBsd6RMkjVDRZzb",
                    },
                    "buffer_size": 100.0,
                },
            },
            "task_config": {"hangup_after_silence": 15.0, "call_terminate": max_duration},
        },
        {
            "task_type": "extraction",
            "toolchain": {"execution": "parallel", "pipelines": [["llm"]]},
            "tools_config": {
                "llm_agent": {
                    "agent_type": "simple_llm_agent",
                    "agent_flow_type": "streaming",
                    "extraction_details": instruction.strip(),
                    "llm_config": {
                        "provider": "openai",
                        "model": settings.BOLNA_LLM_MODEL,
                        "request_json": True,
                    },
                }
            },
            "task_config": {},
        },
    ]

    if webhook_url and not webhook_in_config:
        tasks.append({
            "task_type": "webhook",
            "toolchain": {"execution": "parallel", "pipelines": [["webhook"]]},
            "tools_config": {"api_tools": {"tools_params": {"webhook": {"url": webhook_url, "method": "POST"}}}},
            "task_config": {},
        })

    agent_config = {
        "agent_name": name,
        "agent_type": "other",
        "tasks": tasks,
        "agent_welcome_message": (
            f"Hi! I'm Calthem, an AI assistant calling on behalf of "
            f"{organisation.strip() or 'our team'}. Is this a good time to ask "
            "you a few quick questions?"
        ),
    }
    if webhook_url and webhook_in_config:
        agent_config["webhook_url"] = webhook_url

    return {
        "agent_config": agent_config,
        "agent_prompts": {"task_1": {"system_prompt": system_prompt}},
    }


def build_web_agent_config(
    *,
    name: str,
    instruction: str,
    schema: dict,
    organisation: str = "",
    language: str = "en",
    max_duration: int = 300,
    webhook_url: str | None = None,
    webhook_in_config: bool = False,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    voice_name: str = "George",
) -> dict:
    """Build a Bolna agent config for a BROWSER web call (no telephony).

    Uses input/output provider "default" (the web websocket handlers). The
    browser streams 16kHz PCM in and plays 24kHz PCM back. Same instruction ->
    prompt + extraction pipeline as the telephony config.
    """
    system_prompt = build_conversation_prompt(instruction, schema, organisation)

    tasks: list[dict] = [
        {
            "task_type": "conversation",
            "toolchain": {
                "execution": "parallel",
                "pipelines": [["transcriber", "llm", "synthesizer"]],
            },
            "tools_config": {
                "input": {"format": "pcm", "provider": "default"},
                "output": {"format": "pcm", "provider": "default"},
                "transcriber": {
                    "encoding": "linear16",
                    "language": settings.BOLNA_STT_LANGUAGE or language,
                    "model": settings.BOLNA_STT_MODEL,
                    "provider": settings.BOLNA_STT_PROVIDER,
                    "stream": True,
                    "sampling_rate": 16000,
                },
                "llm_agent": {
                    "agent_type": "simple_llm_agent",
                    "agent_flow_type": "streaming",
                    "llm_config": {
                        "provider": "openai",
                        "model": settings.BOLNA_LLM_MODEL,
                        "request_json": False,
                    },
                },
                "synthesizer": {
                    "audio_format": "pcm",
                    "provider": "elevenlabs",
                    "stream": True,
                    "provider_config": {
                        "voice": voice_name,
                        "model": "eleven_turbo_v2_5",
                        "voice_id": voice_id,
                    },
                    "buffer_size": 100.0,
                    "sampling_rate": 24000,
                },
            },
            "task_config": {"hangup_after_silence": 20.0, "call_terminate": max_duration},
        },
        {
            "task_type": "extraction",
            "toolchain": {"execution": "parallel", "pipelines": [["llm"]]},
            "tools_config": {
                "llm_agent": {
                    "agent_type": "simple_llm_agent",
                    "agent_flow_type": "streaming",
                    "extraction_details": instruction.strip(),
                    "llm_config": {
                        "provider": "openai",
                        "model": settings.BOLNA_LLM_MODEL,
                        "request_json": True,
                    },
                }
            },
            "task_config": {},
        },
    ]

    if webhook_url and not webhook_in_config:
        tasks.append({
            "task_type": "webhook",
            "toolchain": {"execution": "parallel", "pipelines": [["webhook"]]},
            "tools_config": {"api_tools": {"tools_params": {"webhook": {"url": webhook_url, "method": "POST"}}}},
            "task_config": {},
        })

    agent_config = {
        "agent_name": name,
        "agent_type": "other",
        "tasks": tasks,
        "agent_welcome_message": (
            f"Hi! I'm Calthem, an AI assistant"
            f"{' from ' + organisation.strip() if organisation.strip() else ''}. "
            "Is now a good time to ask you a few quick questions?"
        ),
    }
    if webhook_url and webhook_in_config:
        agent_config["webhook_url"] = webhook_url

    return {
        "agent_config": agent_config,
        "agent_prompts": {"task_1": {"system_prompt": system_prompt}},
    }
