"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/call", label: "Calls" },
  { href: "/web-call", label: "Web Call" },
  { href: "/bulk", label: "Contacts" },
  { href: "/results", label: "Results" },
  { href: "/settings", label: "Settings" },
];

export default function Nav() {
  const path = usePathname();
  const isActive = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  return (
    <header className="sticky top-4 z-50 mt-4">
      <div className="glass-strong flex items-center justify-between rounded-full px-4 py-2.5 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-black">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M4 5a2 2 0 0 1 2-2h2l2 5-2 1a11 11 0 0 0 5 5l1-2 5 2v2a2 2 0 0 1-2 2A16 16 0 0 1 4 5Z" />
            </svg>
          </span>
          <span className="text-lg font-semibold tracking-[0.2em] text-white">CALTHEM</span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-full px-4 py-2 text-sm transition ${
                isActive(l.href)
                  ? "bg-white/10 text-white"
                  : "text-white/50 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <Link href="/call" className="btn-primary hidden sm:inline-flex">
          Start a Call
        </Link>
      </div>

      {/* mobile nav */}
      <nav className="glass mt-2 flex items-center justify-between gap-1 rounded-full px-2 py-1.5 md:hidden">
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`flex-1 rounded-full px-2 py-1.5 text-center text-xs transition ${
              isActive(l.href) ? "bg-white/10 text-white" : "text-white/50"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
