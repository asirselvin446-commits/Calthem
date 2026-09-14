export function Transcript({ turns }: { turns: Array<{ role: string; text: string }> }) {
  return (
    <div className="space-y-3">
      {turns.map((t, i) => {
        const ai = t.role === "ai";
        return (
          <div key={i} className={`flex ${ai ? "justify-start" : "justify-end"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
              ai ? "border border-white/10 bg-white/[0.05] text-white/85"
                 : "bg-white text-black"}`}>
              <div className={`mb-0.5 text-[10px] uppercase tracking-wider ${ai ? "text-white/35" : "text-black/40"}`}>
                {ai ? "Calthem" : "Person"}
              </div>
              {t.text}
            </div>
          </div>
        );
      })}
    </div>
  );
}
