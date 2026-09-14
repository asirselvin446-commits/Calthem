"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import type { ParsedImport } from "../lib/types";
import { SectionTitle, StatusPill, Spinner } from "../components/ui";
import SchemaPreview from "../components/SchemaPreview";

export default function BulkPage() {
  const router = useRouter();
  const [parsed, setParsed] = useState<ParsedImport | null>(null);
  const [instruction, setInstruction] = useState("");
  const [org, setOrg] = useState("");
  const [name, setName] = useState("");
  const [concurrency, setConcurrency] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setError(""); setUploading(true);
    try {
      const p = await api.importFile(file);
      setParsed(p);
      if (!name) setName(file.name.replace(/\.[^.]+$/, ""));
    } catch (e: any) {
      setError(e.message || "Could not read the file.");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const create = async () => {
    if (!parsed) return;
    if (instruction.trim().length < 6) return setError("Describe what to collect.");
    setCreating(true); setError("");
    try {
      const contacts = parsed.contacts
        .filter((c) => c.phone_valid)
        .map((c) => ({
          name: c.name, phone: c.phone, email: c.email,
          department: c.department, extra: c.extra,
        }));
      const campaign = await api.createCampaign({
        name: name || "Campaign", mode: "bulk", instruction,
        organisation: org, concurrency, max_retries: 1, contacts,
      });
      router.push(`/campaigns/${campaign.id}?review=1`);
    } catch (e: any) {
      setError(e.message || "Could not create campaign.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="mt-10 max-w-4xl space-y-6">
      <SectionTitle sub="Upload a contact list, describe what to collect, and Calthem calls everyone.">
        Call a list
      </SectionTitle>

      {/* Upload */}
      {!parsed && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={`glass-strong flex cursor-pointer flex-col items-center justify-center gap-3 border-dashed py-20 text-center transition ${
            drag ? "border-white/40 bg-white/[0.08]" : ""}`}
        >
          <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv,.xlsm" hidden
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
          {uploading ? <Spinner className="text-white" /> : (
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/15 bg-white/[0.05]">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 16V4m0 0 4 4m-4-4L8 8" /><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
              </svg>
            </span>
          )}
          <div className="text-lg text-white">Drop your Excel or CSV here</div>
          <div className="text-sm text-white/35">.xlsx · .xls · .csv — click to browse</div>
        </div>
      )}

      {error && <div className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm text-white/70">{error}</div>}

      {/* Preview */}
      {parsed && (
        <>
          <div className="glass p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-medium text-white">{parsed.filename}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-white/40">
                  <Chip>{parsed.stats.total} contacts</Chip>
                  <Chip>{parsed.stats.valid} valid</Chip>
                  {parsed.stats.invalid > 0 && <Chip>{parsed.stats.invalid} invalid</Chip>}
                  {parsed.stats.duplicates > 0 && <Chip>{parsed.stats.duplicates} duplicates</Chip>}
                </div>
              </div>
              <button onClick={() => { setParsed(null); setError(""); }}
                className="btn-ghost">Replace file</button>
            </div>

            {/* detected mapping */}
            <div className="mb-4 flex flex-wrap gap-2 text-xs">
              {Object.entries(parsed.mapping).map(([canon, col]) => (
                <span key={canon} className="rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1 text-white/50">
                  {col} <span className="text-white/25">→</span> <span className="text-white/80">{canon}</span>
                </span>
              ))}
            </div>

            <div className="max-h-80 overflow-auto rounded-2xl border border-white/10">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-ink-800/90 backdrop-blur">
                  <tr className="text-left text-white/40">
                    <th className="px-4 py-2.5 font-medium">Name</th>
                    <th className="px-4 py-2.5 font-medium">Phone</th>
                    <th className="px-4 py-2.5 font-medium">Department</th>
                    <th className="px-4 py-2.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.contacts.slice(0, 100).map((c, i) => (
                    <tr key={i} className="border-t border-white/[0.06]">
                      <td className="px-4 py-2.5 text-white/85">{c.name || "—"}</td>
                      <td className="px-4 py-2.5 text-white/60">{c.phone || "—"}</td>
                      <td className="px-4 py-2.5 text-white/60">{c.department || "—"}</td>
                      <td className="px-4 py-2.5">
                        <StatusPill status={c.phone_valid ? "ready" : "invalid"} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {parsed.errors.length > 0 && (
              <details className="mt-3 text-xs text-white/40">
                <summary className="cursor-pointer">{parsed.errors.length} validation notes</summary>
                <ul className="mt-2 space-y-1">{parsed.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </details>
            )}
          </div>

          {/* Instruction */}
          <div className="glass-strong space-y-5 p-6">
            <div>
              <label className="label">Campaign name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="label">What should Calthem collect?</label>
              <textarea className="input min-h-[110px] resize-y" rows={4}
                placeholder="Call every student and collect their project name, department, team size, current status and whether they need help."
                value={instruction} onChange={(e) => setInstruction(e.target.value)} />
            </div>
            <SchemaPreview instruction={instruction} />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label">Organisation</label>
                <input className="input" value={org} onChange={(e) => setOrg(e.target.value)} />
              </div>
              <div>
                <label className="label">Concurrency</label>
                <select className="input" value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))}>
                  <option value={1}>1 — one at a time (demo)</option>
                  <option value={3}>3</option>
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                </select>
              </div>
            </div>
            <div className="flex items-center justify-between pt-1">
              <p className="text-xs text-white/30">{parsed.stats.valid} people will be called.</p>
              <button onClick={create} disabled={creating} className="btn-primary px-7 py-3">
                {creating ? <Spinner className="text-black" /> : null} Review Campaign
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-white/[0.06] px-2.5 py-1">{children}</span>;
}
