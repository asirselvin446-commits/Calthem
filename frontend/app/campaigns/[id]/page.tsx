"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, subscribeEvents } from "../../lib/api";
import type { Campaign, Call, ResultsResp } from "../../lib/types";
import { SectionTitle, StatusPill, Spinner, MetricCard, fmtDuration } from "../../components/ui";
import { Transcript } from "../../components/Transcript";

type FeedItem = { ts: string; name: string; status: string; call_id: string };

export default function CampaignPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [tab, setTab] = useState<"live" | "results">(
    search.get("review") ? "live" : "live");
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [starting, setStarting] = useState(false);
  const [selectedCall, setSelectedCall] = useState<string | null>(null);
  const refetch = useRef<any>(null);

  const loadCampaign = () => api.getCampaign(id).then(setCampaign).catch(() => {});

  useEffect(() => {
    loadCampaign();
    const unsub = subscribeEvents((e) => {
      if (e.campaign_id && e.campaign_id !== id) return;
      if (e.type === "call_update") {
        if (e.feed) {
          setFeed((f) => [{ ts: e.ts, name: e.contact_name || e.phone || "Contact",
            status: e.status, call_id: e.call_id }, ...f].slice(0, 40));
        }
        // Throttle campaign refetch to keep stats fresh.
        clearTimeout(refetch.current);
        refetch.current = setTimeout(loadCampaign, 400);
      }
      if (e.type === "campaign_update") loadCampaign();
    });
    return () => { unsub(); clearTimeout(refetch.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const start = async () => {
    setStarting(true);
    try { await api.startCampaign(id); await loadCampaign(); }
    catch {} finally { setStarting(false); }
  };
  const pause = async () => { await api.pauseCampaign(id); await loadCampaign(); };

  if (!campaign) return <div className="mt-20 flex justify-center"><Spinner className="text-white/50" /></div>;

  const s = campaign.stats!;
  const notStarted = campaign.status === "draft" || campaign.status === "ready";
  const running = campaign.status === "running";
  const doneCount = s.completed + s.failed + s.no_answer + s.busy;
  const progress = s.total ? Math.round((doneCount / s.total) * 100) : 0;

  return (
    <div className="mt-10 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/results" className="text-sm text-white/40 hover:text-white">← Campaigns</Link>
          <SectionTitle sub={campaign.instruction}>{campaign.name}</SectionTitle>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill status={campaign.status} />
          {notStarted && (
            <button onClick={start} disabled={starting} className="btn-primary px-6 py-2.5">
              {starting ? <Spinner className="text-black" /> : "▶"} Start Calling
            </button>
          )}
          {running && <button onClick={pause} className="btn-ghost">Pause</button>}
          {!running && !notStarted && (
            <button onClick={start} className="btn-ghost">Resume</button>
          )}
        </div>
      </div>

      {/* Review banner */}
      {notStarted && (
        <div className="glass-strong flex flex-wrap items-center justify-between gap-6 p-6">
          <Summary label="Contacts" value={campaign.contact_count ?? s.total} />
          <Summary label="Fields collected" value={campaign.extraction_schema.fields.length} />
          <Summary label="Estimated calls" value={s.total} />
          <Summary label="Concurrency" value={campaign.concurrency} />
          <div className="flex flex-wrap gap-2">
            {campaign.extraction_schema.fields.map((f) => (
              <span key={f.name} className="rounded-lg border border-white/10 bg-white/[0.05] px-2.5 py-1 text-sm text-white/70">
                {f.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Progress metrics */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="Total" value={s.total} />
        <MetricCard label="Completed" value={s.completed} />
        <MetricCard label="In progress" value={s.calling} />
        <MetricCard label="Pending" value={s.pending} />
        <MetricCard label="Failed" value={s.failed} />
        <MetricCard label="No answer" value={s.no_answer} />
      </div>

      {/* Progress bar */}
      <div className="glass p-5">
        <div className="mb-2 flex justify-between text-sm text-white/50">
          <span>{doneCount} of {s.total} processed</span><span>{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
          <div className="h-full rounded-full bg-white transition-all duration-500"
            style={{ width: `${progress}%` }} />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1 w-fit">
        {(["live", "results"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-full px-5 py-2 text-sm capitalize transition ${
              tab === t ? "bg-white text-black" : "text-white/50 hover:text-white"}`}>
            {t === "live" ? "Live activity" : "Results"}
          </button>
        ))}
      </div>

      {tab === "live"
        ? <LiveTab campaignId={id} feed={feed} onOpen={setSelectedCall} />
        : <ResultsTab campaignId={id} onOpen={setSelectedCall} />}

      {selectedCall && (
        <CallModal callId={selectedCall} onClose={() => setSelectedCall(null)} />
      )}
    </div>
  );
}

function Summary({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-white/35">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}

function LiveTab({ campaignId, feed, onOpen }: {
  campaignId: string; feed: FeedItem[]; onOpen: (id: string) => void;
}) {
  const [calls, setCalls] = useState<Call[]>([]);
  useEffect(() => {
    const load = () => api.listCalls(campaignId).then(setCalls).catch(() => {});
    load();
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [campaignId, feed.length]);

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <div className="glass p-5 lg:col-span-2">
        <h3 className="label mb-4">Activity feed</h3>
        {feed.length === 0 ? (
          <p className="text-sm text-white/30">Waiting for calls…</p>
        ) : (
          <div className="space-y-2">
            {feed.map((f, i) => (
              <button key={i} onClick={() => onOpen(f.call_id)}
                className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition hover:bg-white/[0.05]">
                <div className="flex items-center gap-3">
                  <span className="text-xs tabular-nums text-white/30">
                    {new Date(f.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </span>
                  <span className="text-sm text-white/80">{f.name}</span>
                </div>
                <StatusPill status={f.status} />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="glass overflow-hidden lg:col-span-3">
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-ink-800/90 backdrop-blur">
              <tr className="text-left text-white/40">
                <th className="px-4 py-3 font-medium">Contact</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c) => (
                <tr key={c.id} onClick={() => onOpen(c.id)}
                  className="cursor-pointer border-t border-white/[0.06] transition hover:bg-white/[0.04]">
                  <td className="px-4 py-3 text-white/85">{c.contact_name || c.phone}</td>
                  <td className="px-4 py-3"><StatusPill status={c.status} /></td>
                  <td className="px-4 py-3 tabular-nums text-white/50">{fmtDuration(c.duration)}</td>
                </tr>
              ))}
              {calls.length === 0 && (
                <tr><td colSpan={3} className="px-4 py-10 text-center text-white/30">No calls yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ResultsTab({ campaignId, onOpen }: {
  campaignId: string; onOpen: (id: string) => void;
}) {
  const [data, setData] = useState<ResultsResp | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = () => api.results(campaignId, search).then(setData).catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [campaignId, search]);

  if (!data) return <div className="glass p-10 text-center text-white/30">Loading…</div>;

  const dataCols = data.columns.filter((c) => c.name !== "name" && c.name !== "phone");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <input className="input max-w-xs" placeholder="Search results…"
          value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="flex gap-2">
          {["xlsx", "csv", "json"].map((fmt) => (
            <a key={fmt} href={api.exportUrl(campaignId, fmt)}
              className="btn-ghost px-4 py-2 text-sm uppercase">{fmt}</a>
          ))}
        </div>
      </div>

      <div className="glass overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-sm">
            <thead className="bg-ink-800/70">
              <tr className="text-left text-white/40">
                {data.columns.map((c) => (
                  <th key={c.name} className="px-4 py-3 font-medium">{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i} onClick={() => r.call_id && onOpen(r.call_id)}
                  className="cursor-pointer border-t border-white/[0.06] transition hover:bg-white/[0.04]">
                  {data.columns.map((c) => (
                    <td key={c.name} className="px-4 py-3 text-white/80">
                      {c.name === "status" ? <StatusPill status={String(r[c.name] || "pending")} />
                        : formatCell(r[c.name])}
                    </td>
                  ))}
                </tr>
              ))}
              {data.rows.length === 0 && (
                <tr><td colSpan={data.columns.length} className="px-4 py-10 text-center text-white/30">
                  No results yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs text-white/25">{data.rows.length} rows · click a row for the full transcript.</p>
    </div>
  );
}

function formatCell(v: any): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (v.includes && v.includes("T") && /\d{4}-\d{2}-\d{2}T/.test(v)) {
    try { return new Date(v).toLocaleString(); } catch { return String(v); }
  }
  return String(v);
}

function CallModal({ callId, onClose }: { callId: string; onClose: () => void }) {
  const [call, setCall] = useState<Call | null>(null);
  useEffect(() => { api.getCall(callId).then(setCall).catch(() => {}); }, [callId]);

  return (
    <div onClick={onClose}
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-auto bg-black/60 p-4 backdrop-blur-sm sm:p-10">
      <div onClick={(e) => e.stopPropagation()}
        className="glass-strong my-auto w-full max-w-2xl p-6 sm:p-8">
        {!call ? <div className="flex justify-center py-10"><Spinner className="text-white/50" /></div> : (
          <>
            <div className="mb-6 flex items-start justify-between">
              <div>
                <h3 className="text-xl font-semibold text-white">{call.contact_name || call.phone}</h3>
                <div className="mt-1 flex items-center gap-3 text-sm text-white/40">
                  <span>{call.phone}</span><span>·</span><span>{fmtDuration(call.duration)}</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusPill status={call.status} />
                <button onClick={onClose} className="text-white/40 hover:text-white">✕</button>
              </div>
            </div>

            {Object.keys(call.extracted_data || {}).length > 0 && (
              <div className="mb-6">
                <h4 className="label mb-3">Collected information</h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(call.extracted_data).map(([k, v]) => (
                    <div key={k} className="rounded-2xl border border-white/10 bg-white/[0.03] p-3.5">
                      <div className="text-xs uppercase tracking-wider text-white/35">{k.replace(/_/g, " ")}</div>
                      <div className="mt-1 text-white">{Array.isArray(v) ? v.join(", ") : String(v)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {call.error && (
              <div className="mb-6 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/50">
                {call.error}
              </div>
            )}

            {call.transcript && call.transcript.length > 0 && (
              <div>
                <h4 className="label mb-3">Conversation</h4>
                <Transcript turns={call.transcript} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
