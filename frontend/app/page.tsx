"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "./lib/api";
import type { Overview, Campaign } from "./lib/types";
import { MetricCard, StatusPill, Spinner, fmtDuration } from "./components/ui";

export default function OverviewPage() {
  const router = useRouter();
  const [ov, setOv] = useState<Overview | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [seeding, setSeeding] = useState(false);

  const load = () => {
    api.overview().then(setOv).catch(() => {});
    api.listCampaigns().then(setCampaigns).catch(() => {});
  };
  useEffect(load, []);

  const runDemo = async () => {
    setSeeding(true);
    try {
      const c = await api.seedDemo();
      router.push(`/campaigns/${c.id}`);
    } finally {
      setSeeding(false);
    }
  };

  const m = ov?.metrics;

  return (
    <div className="mt-10 space-y-10">
      {/* Hero */}
      <section className="glass-strong relative overflow-hidden p-8 sm:p-12">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/[0.06] blur-3xl" />
        <div className="relative max-w-2xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-white/50">
            <span className="h-1.5 w-1.5 rounded-full bg-white" />
            {ov ? `${ov.adapter === "mock" ? "Demo" : "Live"} mode` : "Connecting…"}
          </div>
          <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl">
            Let AI make<br />the calls.
          </h1>
          <p className="mt-5 max-w-lg text-base text-white/50 sm:text-lg">
            Tell Calthem what you need to know. It calls. It asks. It listens.
            It collects — and hands you structured data.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/call" className="btn-primary px-6 py-3 text-base">Start a Call</Link>
            <Link href="/bulk" className="btn-ghost px-6 py-3 text-base">Upload Contacts</Link>
            <button onClick={runDemo} disabled={seeding}
              className="btn-ghost px-6 py-3 text-base">
              {seeding ? <Spinner className="text-white" /> : "▶"} Run Demo
            </button>
          </div>
        </div>
      </section>

      {/* Metrics */}
      <section>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <MetricCard label="Total Calls" value={m?.total_calls ?? "—"} />
          <MetricCard label="Completed" value={m?.completed ?? "—"} />
          <MetricCard label="Info Collected" value={m?.information_collected ?? "—"} />
          <MetricCard label="Avg Duration" value={m ? fmtDuration(m.avg_duration) : "—"} />
        </div>
      </section>

      {/* Recent campaigns */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-medium text-white">Recent campaigns</h2>
          <Link href="/results" className="text-sm text-white/50 hover:text-white">View all →</Link>
        </div>
        {campaigns.length === 0 ? (
          <div className="glass p-8 text-center text-sm text-white/40">
            No campaigns yet. Start a single call, upload a contact list, or run the demo.
          </div>
        ) : (
          <div className="grid gap-3">
            {campaigns.slice(0, 6).map((c) => (
              <Link key={c.id} href={`/campaigns/${c.id}`}
                className="glass glass-hover flex items-center justify-between gap-4 p-5">
                <div className="min-w-0">
                  <div className="truncate font-medium text-white">{c.name}</div>
                  <div className="mt-0.5 truncate text-sm text-white/40">{c.instruction}</div>
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <div className="hidden gap-1.5 sm:flex">
                    {c.extraction_schema?.fields?.slice(0, 3).map((f) => (
                      <span key={f.name}
                        className="rounded-md bg-white/[0.05] px-2 py-0.5 text-xs text-white/45">
                        {f.label}
                      </span>
                    ))}
                  </div>
                  <StatusPill status={c.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <footer className="pt-6 text-center text-xs text-white/25">
        CALTHEM · AI that calls, asks, listens, and collects. · Calls identify themselves as AI.
      </footer>
    </div>
  );
}
