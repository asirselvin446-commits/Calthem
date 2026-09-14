"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import type { Call } from "../lib/types";
import { SectionTitle, StatusPill, Spinner, fmtDuration } from "../components/ui";
import SchemaPreview from "../components/SchemaPreview";
import { Transcript } from "../components/Transcript";

const ACTIVE = new Set(["preparing", "calling", "ringing", "connected", "in_progress"]);

export default function SingleCallPage() {
  const [phone, setPhone] = useState("");
  const [instruction, setInstruction] = useState("");
  const [org, setOrg] = useState("");
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("en");
  const [maxDuration, setMaxDuration] = useState(180);
  const [showOptions, setShowOptions] = useState(false);

  const [callId, setCallId] = useState<string | null>(null);
  const [call, setCall] = useState<Call | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const pollRef = useRef<any>(null);

  const start = async () => {
    setError("");
    if (!phone.trim()) return setError("Enter a phone number.");
    if (instruction.trim().length < 6) return setError("Describe what to collect.");
    setStarting(true);
    try {
      const res = await api.singleCall({
        phone, instruction, name, organisation: org,
        language, max_duration: maxDuration,
      });
      setCallId(res.call_id);
    } catch (e: any) {
      setError(e.message || "Could not start the call.");
    } finally {
      setStarting(false);
    }
  };

  useEffect(() => {
    if (!callId) return;
    const tick = async () => {
      try {
        const c = await api.getCall(callId);
        setCall(c);
        if (!ACTIVE.has(c.status)) { clearInterval(pollRef.current); }
      } catch {}
    };
    tick();
    pollRef.current = setInterval(tick, 1200);
    return () => clearInterval(pollRef.current);
  }, [callId]);

  const reset = () => { setCallId(null); setCall(null); };

  if (callId) return <LiveCall call={call} onReset={reset} />;

  return (
    <div className="mt-10 max-w-3xl">
      <SectionTitle sub="Enter a number and describe what to find out. Calthem does the rest.">
        Create a call
      </SectionTitle>

      <div className="glass-strong space-y-5 p-6 sm:p-8">
        <div>
          <label className="label">Phone number</label>
          <input className="input" placeholder="+91 98765 43210"
            value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>

        <div>
          <label className="label">What should Calthem find out?</label>
          <textarea className="input min-h-[120px] resize-y" rows={4}
            placeholder="Ask them about their project, team size, department, current progress and challenges."
            value={instruction} onChange={(e) => setInstruction(e.target.value)} />
        </div>

        <SchemaPreview instruction={instruction} />

        <button onClick={() => setShowOptions((s) => !s)}
          className="text-sm text-white/40 hover:text-white/70">
          {showOptions ? "− Hide options" : "+ Voice, language & organisation"}
        </button>

        {showOptions && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Contact name (optional)</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">Organisation</label>
              <input className="input" placeholder="Your team / college"
                value={org} onChange={(e) => setOrg(e.target.value)} />
            </div>
            <div>
              <label className="label">Language</label>
              <select className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="ta">Tamil</option>
              </select>
            </div>
            <div>
              <label className="label">Max duration (seconds)</label>
              <input className="input" type="number" value={maxDuration}
                onChange={(e) => setMaxDuration(Number(e.target.value))} />
            </div>
          </div>
        )}

        {error && <div className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm text-white/70">{error}</div>}

        <div className="flex items-center justify-between gap-4 pt-1">
          <p className="text-xs text-white/30">Calthem will introduce itself as an AI assistant.</p>
          <button onClick={start} disabled={starting} className="btn-primary px-7 py-3">
            {starting ? <Spinner className="text-black" /> : null} Call Now
          </button>
        </div>
      </div>
    </div>
  );
}

function LiveCall({ call, onReset }: { call: Call | null; onReset: () => void }) {
  const status = call?.status || "preparing";
  const state = call?.state || "preparing";
  const active = ACTIVE.has(status);
  const done = status === "completed";

  return (
    <div className="mt-10 max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <SectionTitle>{done ? "Call complete" : "Live call"}</SectionTitle>
        <button onClick={onReset} className="btn-ghost">New call</button>
      </div>

      {/* Live status card */}
      <div className="glass-strong flex flex-col items-center gap-6 p-10 text-center">
        <div className="relative flex h-24 w-24 items-center justify-center">
          {active && <span className="absolute inset-0 rounded-full bg-white/20 animate-pulse-ring" />}
          <span className={`flex h-24 w-24 items-center justify-center rounded-full border ${
            active ? "border-white/30 bg-white/10" : "border-white/15 bg-white/[0.05]"}`}>
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round">
              <path d="M4 5a2 2 0 0 1 2-2h2l2 5-2 1a11 11 0 0 0 5 5l1-2 5 2v2a2 2 0 0 1-2 2A16 16 0 0 1 4 5Z" />
            </svg>
          </span>
        </div>
        <div>
          <StatusPill status={active ? state : status} />
          <div className="mt-4 text-3xl font-semibold tracking-tight text-white">
            {fmtDuration(call?.duration || 0)}
          </div>
          <div className="mt-1 text-sm text-white/40">{call?.phone}</div>
        </div>
        {call?.error && <div className="text-sm text-white/40">{call.error}</div>}
      </div>

      {/* Extracted info */}
      {done && call && Object.keys(call.extracted_data || {}).length > 0 && (
        <div className="glass p-6">
          <h3 className="label mb-4">Collected information</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(call.extracted_data).map(([k, v]) => (
              <div key={k} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="text-xs uppercase tracking-wider text-white/35">{k.replace(/_/g, " ")}</div>
                <div className="mt-1 text-white">{Array.isArray(v) ? v.join(", ") : String(v)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transcript */}
      {call?.transcript && call.transcript.length > 0 && (
        <div className="glass p-6">
          <h3 className="label mb-4">Conversation</h3>
          <Transcript turns={call.transcript} />
        </div>
      )}
    </div>
  );
}
