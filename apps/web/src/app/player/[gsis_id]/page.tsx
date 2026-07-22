import Link from "next/link";
import { Suspense } from "react";
import { scratchpadHref } from "@/features/explore/scoring-url";
import { PlayerSheet } from "@/features/player-sheet/PlayerSheet";

type Params = { gsis_id: string };
type SearchParams = {
  scoring_preset?: string | string[];
  scoring_rules?: string | string[];
};

function firstParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) return value[0] ?? null;
  return value ?? null;
}

export async function generateMetadata({ params }: { params: Promise<Params> }) {
  const { gsis_id } = await params;
  return {
    title: `Player — Razzle`,
    description: `Week-by-week film on ${gsis_id}`,
  };
}

export default async function PlayerPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<SearchParams>;
}) {
  const { gsis_id } = await params;
  const sp = await searchParams;
  const exitHref = scratchpadHref({
    scoring_preset: firstParam(sp.scoring_preset) ?? "standard",
    scoring_rules: firstParam(sp.scoring_rules),
  });

  return (
    <main style={{ minHeight: "100vh", background: "var(--bg)" }}>
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
          href={exitHref}
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink-medium)",
            textDecoration: "none",
          }}
        >
          Scratchpad
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
