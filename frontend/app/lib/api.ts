import type {
  SchemaResp, ParsedImport, Campaign, Call, ResultsResp, Overview,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8090";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // Bypass ngrok's free-tier browser interstitial for API (JSON) calls.
      "ngrok-skip-browser-warning": "true",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  overview: () => req<Overview>("/api/overview"),

  previewSchema: (instruction: string) =>
    req<SchemaResp>("/api/schema/preview", {
      method: "POST", body: JSON.stringify({ instruction }),
    }),

  importFile: async (file: File): Promise<ParsedImport> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/api/import`, {
      method: "POST", body: fd,
      headers: { "ngrok-skip-browser-warning": "true" },
    });
    if (!res.ok) {
      let d = res.statusText;
      try { d = (await res.json()).detail || d; } catch {}
      throw new Error(d);
    }
    return res.json();
  },

  createCampaign: (payload: any) =>
    req<Campaign>("/api/campaigns", { method: "POST", body: JSON.stringify(payload) }),

  listCampaigns: () => req<Campaign[]>("/api/campaigns"),
  getCampaign: (id: string) => req<Campaign>(`/api/campaigns/${id}`),
  startCampaign: (id: string) =>
    req<any>(`/api/campaigns/${id}/start`, { method: "POST" }),
  pauseCampaign: (id: string) =>
    req<any>(`/api/campaigns/${id}/pause`, { method: "POST" }),
  campaignContacts: (id: string) =>
    req<any[]>(`/api/campaigns/${id}/contacts`),

  singleCall: (payload: any) =>
    req<any>("/api/calls/single", { method: "POST", body: JSON.stringify(payload) }),
  getCall: (id: string) => req<Call>(`/api/calls/${id}`),
  listCalls: (campaignId: string) =>
    req<Call[]>(`/api/calls?campaign_id=${campaignId}`),

  results: (id: string, search = "", status = "") =>
    req<ResultsResp>(
      `/api/campaigns/${id}/results?search=${encodeURIComponent(search)}&status=${status}`),
  exportUrl: (id: string, format: string) =>
    `${API_BASE}/api/campaigns/${id}/export?format=${format}`,

  seedDemo: () => req<Campaign>("/api/demo/seed", { method: "POST" }),

  startWebCall: (payload: {
    instruction: string; name?: string; organisation?: string; language?: string;
  }) => req<{
    call_id: string; campaign_id: string; agent_id: string;
    ws_url: string; extraction_schema: SchemaResp; welcome: string;
  }>("/api/web-call/start", { method: "POST", body: JSON.stringify(payload) }),

  finishWebCall: (callId: string, payload: {
    transcript: Array<{ role: string; text: string }>; status?: string; duration?: number;
  }) => req<any>(`/api/web-call/${callId}/finish`, {
    method: "POST", body: JSON.stringify(payload),
  }),
};

export function subscribeEvents(onEvent: (e: any) => void): () => void {
  const es = new EventSource(`${API_BASE}/api/events/stream`);
  es.onmessage = (ev) => {
    try { onEvent(JSON.parse(ev.data)); } catch {}
  };
  es.onerror = () => { /* browser auto-reconnects */ };
  return () => es.close();
}
