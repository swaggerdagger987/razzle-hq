import Link from "next/link";
import { Suspense } from "react";
import { ScreenerPanel } from "@/features/explore/ScreenerPanel";

export const metadata = {
  title: "Explore — Razzle",
  description: "Season-total screener over real NFL data. Filter by position, sort any column.",
};

export default function ExplorePage() {
  return (
    <main style={{ minHeight: "100vh", background: "var(--bg)" }}>
      {/* Hallway nav */}
      <nav
        style={{
          display: "flex",
          gap: "16px",
          padding: "12px 24px",
          borderBottom: "2px dashed var(--ink-faint)",
        }}
      >
        <Link
          href="/"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink-medium)",
            textDecoration: "none",
          }}
        >
          ← Razzle
        </Link>
        <Link
          href="/scoring"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink-medium)",
            textDecoration: "none",
          }}
        >
          Scoring
        </Link>
      </nav>

      <Suspense
        fallback={
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "24px",
              color: "var(--ink-light)",
              padding: "48px 24px",
            }}
          >
            pulling film...
          </p>
        }
      >
        <ScreenerPanel />
      </Suspense>
    </main>
  );
}
