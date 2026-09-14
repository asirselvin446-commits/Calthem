"use client";

import React from "react";

// Monochrome status vocabulary -> dot intensity + label.
const STATUS_META: Record<string, { label: string; dot: string; text: string }> = {
  // contact / call
  pending: { label: "Pending", dot: "bg-white/30", text: "text-white/50" },
  ready: { label: "Ready", dot: "bg-white/40", text: "text-white/60" },
  preparing: { label: "Preparing", dot: "bg-white/40", text: "text-white/60" },
  calling: { label: "Calling", dot: "bg-white animate-pulse", text: "text-white" },
  ringing: { label: "Ringing", dot: "bg-white animate-pulse", text: "text-white" },
  connected: { label: "Connected", dot: "bg-white animate-pulse", text: "text-white" },
  in_progress: { label: "In progress", dot: "bg-white animate-pulse", text: "text-white" },
  ai_speaking: { label: "AI speaking", dot: "bg-white animate-pulse", text: "text-white" },
  listening: { label: "Listening", dot: "bg-white animate-pulse", text: "text-white" },
  processing: { label: "Processing", dot: "bg-white/70 animate-pulse", text: "text-white/80" },
  completed: { label: "Completed", dot: "bg-white", text: "text-white" },
  running: { label: "Running", dot: "bg-white animate-pulse", text: "text-white" },
  paused: { label: "Paused", dot: "bg-white/40", text: "text-white/60" },
  failed: { label: "Failed", dot: "bg-white/25", text: "text-white/40" },
  no_answer: { label: "No answer", dot: "bg-white/25", text: "text-white/40" },
  busy: { label: "Busy", dot: "bg-white/25", text: "text-white/40" },
  invalid: { label: "Invalid", dot: "bg-white/20", text: "text-white/35" },
  draft: { label: "Draft", dot: "bg-white/30", text: "text-white/50" },
};

export function StatusPill({ status }: { status: string }) {
  const m = STATUS_META[status] || { label: status, dot: "bg-white/30", text: "text-white/50" };
  return (
    <span className={`pill border border-white/10 bg-white/[0.04] ${m.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {m.label}
    </span>
  );
}

export function MetricCard({
  label, value, sub,
}: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="glass glass-hover p-5">
      <div className="label mb-3">{label}</div>
      <div className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">{value}</div>
      {sub && <div className="mt-1 text-xs text-white/40">{sub}</div>}
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function SectionTitle({ children, sub }: { children: React.ReactNode; sub?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{children}</h1>
      {sub && <p className="mt-1.5 text-sm text-white/45">{sub}</p>}
    </div>
  );
}

export function TypeBadge({ type }: { type: string }) {
  return (
    <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white/40">
      {type}
    </span>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="glass flex flex-col items-center justify-center gap-2 py-16 text-center">
      <div className="text-white/60">{title}</div>
      {hint && <div className="max-w-sm text-sm text-white/35">{hint}</div>}
    </div>
  );
}

export function fmtDuration(seconds: number): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}
