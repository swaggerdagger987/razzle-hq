"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchAdjacentPlayers } from "./api";

type Props = {
  gsis_id: string;
  season: number;
  position: string;
};

export function PrevNextNav({ gsis_id, season, position }: Props) {
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["adjacent", gsis_id, season, position],
    queryFn: () => fetchAdjacentPlayers(gsis_id, season, position),
    staleTime: 60_000,
  });

  const prev = data?.prev_gsis_id;
  const next = data?.next_gsis_id;

  if (isLoading) {
    return (
      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
        <span
          style={{
            fontFamily: "var(--font-hand)",
            fontSize: "16px",
            color: "var(--ink-faint)",
          }}
        >
          loading nav...
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
      <button
        className="btn-chunky"
        disabled={!prev}
        onClick={() => {
          if (prev) router.push(`/player/${encodeURIComponent(prev)}`);
        }}
        style={{
          opacity: prev ? 1 : 0.35,
          cursor: prev ? "pointer" : "default",
          fontSize: "13px",
          padding: "6px 14px",
        }}
        aria-label="Previous player"
      >
        ← Prev
      </button>

      <button
        className="btn-chunky"
        disabled={!next}
        onClick={() => {
          if (next) router.push(`/player/${encodeURIComponent(next)}`);
        }}
        style={{
          opacity: next ? 1 : 0.35,
          cursor: next ? "pointer" : "default",
          fontSize: "13px",
          padding: "6px 14px",
        }}
        aria-label="Next player"
      >
        Next →
      </button>
    </div>
  );
}
