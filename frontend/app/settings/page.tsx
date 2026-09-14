"use client";

import { useEffect, useState } from "react";
import { api, API_BASE } from "../lib/api";
import type { Overview } from "../lib/types";
import { SectionTitle } from "../components/ui";

export default function SettingsPage() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    api.overview().then((o) => { setOv(o); setOk(true); }).catch(() => setOk(false));
  }, []);

  return (
    <div className="mt-10 max-w-3xl space-y-6">
      <SectionTitle sub="Connection, calling mode and responsible-use.">Settings</SectionTitle>

      <div className="glass space-y-4 p-6">
        <Row label="Backend">
          <span className="text-white/70">{API_BASE}</span>
        </Row>
        <Row label="Connection">
          <span className={ok ? "text-white" : "text-white/40"}>
            {ok === null ? "Checking…" : ok ? "● Connected" : "○ Offline"}
          </span>
        </Row>
        <Row label="Calling mode">
          <span className="rounded-lg border border-white/10 bg-white/[0.05] px-3 py-1 text-sm text-white/80">
            {ov?.adapter === "mock" ? "Mock — simulated caller (no telephony)" : "Bolna — live calls"}
          </span>
        </Row>
      </div>

      <div className="glass p-6">
        <h3 className="mb-3 font-medium text-white">Responsible use</h3>
        <ul className="space-y-2 text-sm text-white/50">
          <li>• Calthem always introduces itself as an AI assistant on every call.</li>
          <li>• Only call people who have agreed to receive calls.</li>
          <li>• In mock mode, no real phone calls are placed — all activity is simulated.</li>
          <li>• Switch to live calling by setting <code className="text-white/70">TELEPHONY_ADAPTER=bolna</code> in the backend and configuring a telephony provider.</li>
        </ul>
      </div>

      <div className="glass p-6">
        <h3 className="mb-3 font-medium text-white">Going live with Bolna</h3>
        <p className="text-sm text-white/45">
          Calthem drives the open-source Bolna voice platform. To make real calls,
          run the Bolna server + a telephony provider (Twilio/Plivo) with ngrok,
          set <code className="text-white/70">BOLNA_API_URL</code>,{" "}
          <code className="text-white/70">TELEPHONY_API_URL</code> and{" "}
          <code className="text-white/70">CALTHEM_WEBHOOK_BASE</code>, then restart the
          backend with <code className="text-white/70">TELEPHONY_ADAPTER=bolna</code>.
        </p>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.06] pb-4 last:border-0 last:pb-0">
      <span className="text-sm text-white/40">{label}</span>
      {children}
    </div>
  );
}
