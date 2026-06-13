"use client";

import { useQuery } from "@tanstack/react-query";
import { parseAsInteger, parseAsStringLiteral, useQueryStates } from "nuqs";
import { fetchScreener, type Position } from "./api";
import { ScreenerTable } from "./ScreenerTable";

const POSITIONS: Position[] = ["QB", "RB", "WR", "TE"];
const POS_TOKEN: Record<string, string> = {
  QB: "var(--pos-qb)",
  RB: "var(--pos-rb)",
  WR: "var(--pos-wr)",
  TE: "var(--pos-te)",
};

const SORT_KEYS = [
  "name",
  "games",
  "pass_att",
  "pass_cmp",
  "pass_yd",
  "pass_td",
  "pass_int",
  "rush_att",
  "rush_yd",
  "rush_td",
  "target",
  "rec",
  "rec_yd",
  "rec_td",
  "fumble_lost",
] as const;

type SortKey = (typeof SORT_KEYS)[number];

export function ScreenerPanel() {
  const [params, setParams] = useQueryStates({
    season: parseAsInteger.withDefault(2025),
    position: parseAsStringLiteral(POSITIONS),
    sort: parseAsStringLiteral(SORT_KEYS).withDefault("name"),
    dir: parseAsStringLiteral(["asc", "desc"] as const).withDefault("asc"),
  });

  const { season, position, sort, dir } = params;

  const { data, isPending, isError } = useQuery({
    queryKey: ["screener", season, position, sort, dir],
    queryFn: () =>
      fetchScreener({
        season,
        position: position as Position | null,
        sort,
        dir: dir as "asc" | "desc",
        limit: 100,
        offset: 0,
      }),
  });

  function handleSortChange(key: string, nextDir: "asc" | "desc") {
    void setParams({ sort: key as SortKey, dir: nextDir });
  }

  function handlePositionClick(pos: Position) {
    void setParams({ position: position === pos ? null : pos });
  }

  return (
    <section
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "32px 24px",
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
          marginBottom: "20px",
        }}
      >
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "32px",
            margin: 0,
            marginRight: "8px",
          }}
        >
          Explore
        </h1>

        {POSITIONS.map((pos) => (
          <button
            key={pos}
            onClick={() => handlePositionClick(pos)}
            className="btn-chunky"
            data-active={position === pos}
            style={
              position === pos
                ? {
                    background: POS_TOKEN[pos],
                    color: "var(--text-on-accent)",
                    borderColor: "var(--ink)",
                  }
                : undefined
            }
          >
            {pos}
          </button>
        ))}

        <span
          style={{
            marginLeft: "auto",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            color: "var(--ink-light)",
          }}
        >
          {data ? `${data.total} players · ${season}` : null}
        </span>
      </div>

      {/* States */}
      {isPending && (
        <p
          style={{
            fontFamily: "var(--font-hand)",
            fontSize: "24px",
            color: "var(--ink-light)",
            padding: "48px 0",
          }}
        >
          pulling film...
        </p>
      )}

      {isError && !isPending && (
        <div
          className="card-chunky"
          style={{ padding: "32px", textAlign: "center" }}
        >
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "24px",
              color: "var(--red)",
            }}
          >
            film room&apos;s dark. try again.
          </p>
        </div>
      )}

      {data && data.rows.length === 0 && (
        <div
          className="card-chunky"
          style={{ padding: "32px", textAlign: "center" }}
        >
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "24px",
              color: "var(--ink-light)",
            }}
          >
            no players match that cut.
          </p>
        </div>
      )}

      {data && data.rows.length > 0 && (
        <ScreenerTable
          rows={data.rows}
          sortKey={sort}
          sortDir={dir as "asc" | "desc"}
          onSortChange={handleSortChange}
        />
      )}
    </section>
  );
}
