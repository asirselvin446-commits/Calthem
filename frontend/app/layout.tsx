import "./globals.css";
import type { Metadata } from "next";
import Nav from "./components/Nav";

export const metadata: Metadata = {
  title: "CALTHEM — AI that calls, asks, listens, and collects.",
  description: "Turn phone conversations into structured data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="grain">
        <div className="relative z-10 mx-auto max-w-7xl px-5 pb-24 sm:px-8">
          <Nav />
          <main className="animate-fade-up">{children}</main>
        </div>
      </body>
    </html>
  );
}
