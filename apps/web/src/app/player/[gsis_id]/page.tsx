import Link from "next/link";
import { Suspense } from "react";
import { PlayerSheet } from "@/features/player-sheet/PlayerSheet";

type Params = { gsis_id: string };

export async function generateMetadata({ params }: { params: Promise<Params> }) {
  const { gsis_id } = await params;
  return {
    title: `Player — Razzle`,
    description: `Week-by-week film on ${gsis_id}`,
  };
}

export default async function PlayerPage({ params }: { params: Promise<Params> }) {
  const { gsis_id } = await params;

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
          href="/explore"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink-medium)",
            textDecoration: "none",
          }}
        >
          Explore
        </Link>
      </nav>

      <Suspense
        fallback={
          <div style={{ padding: "48px 24px" }}>
            <p
              style={{
                fontFamily: "var(--font-hand)",
                fontSize: "28px",
                color: "var(--ink-light)",
              }}
            >
              pulling up the tape...
            </p>
          </div>
        }
      >
        <PlayerSheet gsis_id={gsis_id} />
      </Suspense>
    </main>
  );
}
