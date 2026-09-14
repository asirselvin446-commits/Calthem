"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import type { Campaign } from "../lib/types";
import { SectionTitle, StatusPill, Empty } from "../components/ui";

export default function ResultsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.listCampaigns().then(setCampaigns).catch(() => {}).finally(() => setLoaded(true));
  }, []);

  return (
    <div className="mt-10 space-y-6">
      <SectionTitle sub="Every campaign and its collected data.">Results</SectionTitle>

      {loaded && campaigns.length === 0 ? (
        <Empty title="No campaigns yet"
          hint="Start a single call or upload a contact list to begin collecting data." />
      ) : (
        <div className="grid gap-3">
          {campaigns.map((c) => (
            <Link key={c.id} href={`/campaigns/${c.id}`}
              className="glass glass-hover flex items-center justify-between gap-4 p-5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium text-white">{c.name}</span>
                  <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-white/40">
                    {c.mode}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-sm text-white/40">{c.instruction}</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {c.extraction_schema?.fields?.map((f) => (
                    <span key={f.name} className="rounded bg-white/[0.05] px-1.5 py-0.5 text-xs text-white/40">
                      {f.label}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <span className="text-xs text-white/30">
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
                <StatusPill status={c.status} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
