"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { parseAsString, useQueryState } from "nuqs";
import { fetchPlayerDetail } from "./api";
import { PlayerHeader } from "./PlayerHeader";
import { StatTable } from "./StatTable";
import { PrevNextNav } from "./PrevNextNav";

type Props = {
  gsis_id: string;
};

export function PlayerSheet({ gsis_id }: Props) {
  const [scoringPreset] = useQueryState("scoring_preset", parseAsString.withDefault("standard"));
  const [scoringRules] = useQueryState("scoring_rules", parseAsString);
  const scoringLabel = scoringRules ? "custom" : scoringPreset;

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["player", gsis_id],
    queryFn: () => fetchPlayerDetail(gsis_id),
    retry: false,
  });

  const isNotFound = isError && error instanceof Error && error.message === "player not found";

  const [activeSeason, setActiveSeason] = useState<number | null>(null);

  const seasons = data?.seasons ?? [];
  const defaultSeason = seasons[0]?.season ?? 2025;
  const selectedSeason = activeSeason ?? defaultSeason;
  const seasonData = seasons.find((s) => s.season === selectedSeason);

  if (isPending) {
    return (
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
    );
  }

  if (isNotFound) {
    return (
      <div style={{ padding: "48px 24px" }}>
        <div
          className="card-chunky"
          style={{ padding: "40px", textAlign: "center", maxWidth: "480px", margin: "0 auto" }}
        >
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "28px",
              color: "var(--ink-light)",
            }}
          >
            player not found.
          </p>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "13px",
              color: "var(--ink-faint)",
              marginTop: "12px",
            }}
          >
            check the ID or head back to Scratchpad.
          </p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ padding: "48px 24px" }}>
        <div
          className="card-chunky"
          style={{ padding: "40px", textAlign: "center", maxWidth: "480px", margin: "0 auto" }}
        >
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "28px",
              color: "var(--red)",
            }}
          >
            film room&apos;s dark. try again.
          </p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "32px 24px" }}>
      <div style={{ marginBottom: "28px" }}>
        <PlayerHeader name={data.name} position={data.position} team={data.team} />
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          flexWrap: "wrap",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "6px",
            flexWrap: "wrap",
          }}
        >
          {seasons.map((s) => (
            <button
              key={s.season}
              className="btn-chunky"
              onClick={() => setActiveSeason(s.season)}
              data-active={s.season === selectedSeason}
              style={
                s.season === selectedSeason
                  ? {
                      background: "var(--orange)",
                      color: "var(--text-on-accent)",
                      borderColor: "var(--ink)",
                      fontSize: "13px",
                      padding: "5px 14px",
                    }
                  : { fontSize: "13px", padding: "5px 14px" }
              }
            >
              {s.season}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        <PrevNextNav
          gsis_id={gsis_id}
          season={selectedSeason}
          position={data.position}
          scoringPreset={scoringPreset}
          scoringRules={scoringRules}
        />
      </div>

      {seasonData && (
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            color: "var(--ink-light)",
            marginBottom: "14px",
          }}
        >
          {seasonData.week_stats.length} week{seasonData.week_stats.length !== 1 ? "s" : ""} of film
          {" · "}
          <span style={{ color: "var(--orange)", fontWeight: 600 }}>{scoringLabel}</span>
        </p>
      )}

      {seasonData ? (
        <StatTable weekStats={seasonData.week_stats} />
      ) : (
        <p
          style={{
            fontFamily: "var(--font-hand)",
            fontSize: "22px",
            color: "var(--ink-light)",
            padding: "24px 0",
          }}
        >
          no film available for this season.
        </p>
      )}
    </div>
  );
}
