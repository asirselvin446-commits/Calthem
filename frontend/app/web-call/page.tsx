"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import { WebVoiceCall } from "../lib/webAudioCall";
import type { Field } from "../lib/types";
import { SectionTitle, StatusPill, Spinner } from "../components/ui";
import SchemaPreview from "../components/SchemaPreview";

type Turn = { role: string; text: string };

export default function WebCallPage() {
  const [instruction, setInstruction] = useState("");
  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const [language, setLanguage] = useState("en");

  const [phase, setPhase] = useState<"form" | "connecting" | "live" | "ended">("form");
  const [status, setStatus] = useState("connected");
  const [micOn, setMicOn] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const [callId, setCallId] = useState<string | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [startedAt, setStartedAt] = useState(0);

  const callRef = useRef<WebVoiceCall | null>(null);
  const turnsRef = useRef<Turn[]>([]);
  // Accumulate streamed AI text into a single growing turn until the next event lull.
  const aiBufRef = useRef<string>("");
  const aiTimerRef = useRef<any>(null);

  const pushTurn = (t: Turn) => {
    turnsRef.current = [...turnsRef.current, t];
    setTurns(turnsRef.current);
  };

  const flushAi = () => {
    const text = aiBufRef.current.trim();
    aiBufRef.current = "";
    if (text) pushTurn({ role: "ai", text });
  };

  const start = async () => {
    setError("");
    if (instruction.trim().length < 6) return setError("Describe what to collect.");
    setPhase("connecting");
    try {
      const res = await api.startWebCall({ instruction, name, organisation: org, language });
      setCallId(res.call_id);
      setFields(res.extraction_schema.fields || []);
      setStartedAt(Date.now());

      const call = new WebVoiceCall(res.ws_url, {
        onOpen: () => { setPhase("live"); setStatus("connected"); },
        onStatus: (s) => setStatus(s),
        onAiText: (t) => {
          aiBufRef.current += t;
          clearTimeout(aiTimerRef.current);
          aiTimerRef.current = setTimeout(flushAi, 700);
        },
        onError: (m) => setError(m),
        onClose: () => setStatus("completed"),
      });
      callRef.current = call;
      await call.connect();
      // Auto-enable the mic (requires the click that triggered this handler).
      try { await call.startMic(); setMicOn(true); } catch { /* user can enable manually */ }
    } catch (e: any) {
      setError(e.message || "Could not start the web call.");
      setPhase("form");
    }
  };

  const toggleMic = async () => {
    const call = callRef.current;
    if (!call) return;
    if (micOn) { call.stopMic(); setMicOn(false); }
    else { try { await call.startMic(); setMicOn(true); } catch (e: any) { setError("Microphone blocked: " + e.message); } }
  };

  const sendTyped = () => {
    const t = typed.trim();
    if (!t || !callRef.current) return;
    callRef.current.sendText(t);
    pushTurn({ role: "person", text: t });
    setTyped("");
  };

  const end = async () => {
    flushAi();
    callRef.current?.close();
    setMicOn(false);
    setPhase("ended");
    setStatus("completed");
    if (callId) {
      const duration = startedAt ? (Date.now() - startedAt) / 1000 : 0;
      try { await api.finishWebCall(callId, { transcript: turnsRef.current, duration, status: "completed" }); } catch {}
    }
  };

  useEffect(() => () => { callRef.current?.close(); }, []);

  if (phase === "form") {
    return (
      <div className="mt-10 max-w-3xl">
        <SectionTitle sub="Talk to Calthem through your microphone — a real AI voice conversation, no phone needed.">
          Web voice call
        </SectionTitle>
        <div className="glass-strong space-y-5 p-6 sm:p-8">
          <div>
            <label className="label">What should Calthem find out?</label>
            <textarea className="input min-h-[110px] resize-y" rows={4}
              placeholder="Ask about my project, department, team size and current progress."
              value={instruction} onChange={(e) => setInstruction(e.target.value)} />
          </div>
          <SchemaPreview instruction={instruction} />
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="label">Your name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">Organisation</label>
              <input className="input" value={org} onChange={(e) => setOrg(e.target.value)} />
            </div>
            <div>
              <label className="label">Language</label>
              <select className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="ta">Tamil</option>
              </select>
            </div>
          </div>
          {error && <div className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm text-white/70">{error}</div>}
          <div className="flex items-center justify-between pt-1">
            <p className="text-xs text-white/30">Requires the Bolna engine running with your API keys.</p>
            <button onClick={start} className="btn-primary px-7 py-3">Start Web Call</button>
          </div>
        </div>
      </div>
    );
  }

  const live = phase === "live" || phase === "connecting";

  return (
    <div className="mt-10 max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <SectionTitle>{phase === "ended" ? "Call ended" : "Web voice call"}</SectionTitle>
        {phase === "ended"
          ? <Link href={callId ? `#` : "/"} className="btn-ghost" onClick={() => location.reload()}>New call</Link>
          : <button onClick={end} className="btn-ghost">End call</button>}
      </div>

      {/* Orb */}
      <div className="glass-strong flex flex-col items-center gap-6 p-10 text-center">
        <div className="relative flex h-28 w-28 items-center justify-center">
          {status !== "completed" && <span className="absolute inset-0 rounded-full bg-white/15 animate-pulse-ring" />}
          <span className={`flex h-28 w-28 items-center justify-center rounded-full border ${
            status === "ai_speaking" ? "border-white/40 bg-white/15" : "border-white/20 bg-white/[0.05]"}`}>
            <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" strokeLinecap="round">
              <path d="M12 3v18M8 7v10M16 7v10M4 10v4M20 10v4" />
            </svg>
          </span>
        </div>
        {phase === "connecting" ? (
          <div className="flex items-center gap-2 text-white/60"><Spinner className="text-white/60" /> Connecting…</div>
        ) : (
          <StatusPill status={status} />
        )}
        {fields.length > 0 && (
          <div className="flex flex-wrap justify-center gap-2">
            {fields.map((f) => (
              <span key={f.name} className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-xs text-white/50">{f.label}</span>
            ))}
          </div>
        )}
      </div>

      {error && <div className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm text-white/70">{error}</div>}

      {/* Controls */}
      {live && (
        <div className="glass flex flex-wrap items-center gap-3 p-4">
          <button onClick={toggleMic}
            className={micOn ? "btn-primary px-5 py-2.5" : "btn-ghost px-5 py-2.5"}>
            {micOn ? "🎙 Mic on — tap to mute" : "🎙 Enable microphone"}
          </button>
          <div className="flex flex-1 items-center gap-2">
            <input className="input flex-1" placeholder="…or type your reply (works without a mic)"
              value={typed} onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendTyped()} />
            <button onClick={sendTyped} className="btn-ghost px-4 py-2.5">Send</button>
          </div>
        </div>
      )}

      {/* Transcript */}
      <div className="glass p-6">
        <h3 className="label mb-4">Conversation</h3>
        {turns.length === 0 ? (
          <p className="text-sm text-white/30">
            {live ? "Say hello — Calthem will greet you and start asking." : "No transcript captured."}
          </p>
        ) : (
          <div className="space-y-3">
            {turns.map((t, i) => {
              const ai = t.role === "ai";
              return (
                <div key={i} className={`flex ${ai ? "justify-start" : "justify-end"}`}>
                  <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                    ai ? "border border-white/10 bg-white/[0.05] text-white/85" : "bg-white text-black"}`}>
                    <div className={`mb-0.5 text-[10px] uppercase tracking-wider ${ai ? "text-white/35" : "text-black/40"}`}>
                      {ai ? "Calthem" : "You"}
                    </div>
                    {t.text}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <p className="mt-4 text-xs text-white/25">
          Note: your spoken words are transcribed on the server; typed replies appear here directly.
        </p>
      </div>

      {phase === "ended" && callId && (
        <div className="glass flex items-center justify-between p-5">
          <span className="text-sm text-white/50">Extracted data appears in Results once processing finishes.</span>
          <Link href="/results" className="btn-ghost">View results</Link>
        </div>
      )}
    </div>
  );
}
