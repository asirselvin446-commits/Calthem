"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Field } from "../lib/types";
import { TypeBadge } from "./ui";

/** Debounced live preview of the extraction schema derived from an instruction. */
export default function SchemaPreview({
  instruction, onSchema,
}: { instruction: string; onSchema?: (f: Field[]) => void }) {
  const [fields, setFields] = useState<Field[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const text = instruction.trim();
    if (text.length < 6) { setFields([]); onSchema?.([]); return; }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const s = await api.previewSchema(text);
        setFields(s.fields);
        onSchema?.(s.fields);
      } catch { /* ignore */ }
      finally { setLoading(false); }
    }, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instruction]);

  if (!instruction.trim()) return null;

  return (
    <div className="glass p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="label mb-0">Calthem will collect</span>
        {loading && <span className="text-xs text-white/30">analysing…</span>}
      </div>
      {fields.length === 0 ? (
        <p className="text-sm text-white/35">
          Describe what to find out and the fields will appear here.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {fields.map((f) => (
            <span key={f.name}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.05] px-3 py-1.5 text-sm text-white/80">
              {f.label}
              <TypeBadge type={f.type} />
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
