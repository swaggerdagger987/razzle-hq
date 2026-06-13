"use client";

import type { WeekStats } from "./api";

type Props = {
  weekStats: WeekStats[];
};

// The 13 stats referenced in S-003 (plus week)
const STAT_DEFS: { key: keyof WeekStats; label: string; decimals?: number }[] = [
  { key: "pass_att", label: "Att" },
  { key: "pass_cmp", label: "Cmp" },
  { key: "pass_yd", label: "PaYd" },
  { key: "pass_td", label: "PaTD" },
  { key: "pass_int", label: "INT" },
  { key: "rush_att", label: "Car" },
  { key: "rush_yd", label: "RuYd" },
  { key: "rush_td", label: "RuTD" },
  { key: "target", label: "Tgt" },
  { key: "rec", label: "Rec" },
  { key: "rec_yd", label: "ReYd" },
  { key: "rec_td", label: "ReTD" },
  { key: "fumble_lost", label: "FL" },
];

// Show only columns where at least one row has a non-zero value.
function relevantStats(rows: WeekStats[]) {
  return STAT_DEFS.filter((def) => rows.some((r) => r[def.key] !== 0));
}

function fmt(v: number) {
  if (v === 0) return <span style={{ color: "var(--ink-faint)" }}>—</span>;
  return Math.round(v) === v ? String(v) : v.toFixed(1);
}

export function StatTable({ weekStats }: Props) {
  const cols = relevantStats(weekStats).length > 0 ? relevantStats(weekStats) : STAT_DEFS.slice(0, 6);

  if (weekStats.length === 0) {
    return (
      <p
        style={{
          fontFamily: "var(--font-hand)",
          fontSize: "22px",
          color: "var(--ink-light)",
          padding: "32px 0",
        }}
      >
        no film available for this season.
      </p>
    );
  }

  return (
    <div
      style={{
        overflowX: "auto",
        borderRadius: "var(--radius)",
        border: "3px solid var(--ink)",
        boxShadow: "var(--shadow-chunky)",
        background: "var(--bg-card)",
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", minWidth: "480px" }}>
        <thead>
          <tr style={{ background: "var(--bg-warm)" }}>
            <th
              style={{
                padding: "10px 14px",
                fontFamily: "var(--font-display)",
                fontSize: "11px",
                textTransform: "uppercase",
                textAlign: "center",
                borderBottom: "3px solid var(--ink)",
                color: "var(--ink)",
                whiteSpace: "nowrap",
              }}
            >
              Wk
            </th>
            {cols.map((def) => (
              <th
                key={def.key}
                style={{
                  padding: "10px 14px",
                  fontFamily: "var(--font-display)",
                  fontSize: "11px",
                  textTransform: "uppercase",
                  textAlign: "right",
                  borderBottom: "3px solid var(--ink)",
                  color: "var(--ink)",
                  whiteSpace: "nowrap",
                }}
              >
                {def.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weekStats.map((row, idx) => (
            <tr
              key={row.week}
              style={{
                background: idx % 2 === 1 ? "var(--zebra-stripe)" : undefined,
              }}
            >
              <td
                style={{
                  padding: "8px 14px",
                  fontFamily: "var(--font-display)",
                  fontSize: "13px",
                  textAlign: "center",
                  borderBottom: "1px solid var(--ink-faint)",
                  color: "var(--ink-medium)",
                  fontWeight: 700,
                }}
              >
                {row.week}
              </td>
              {cols.map((def) => (
                <td
                  key={def.key}
                  style={{
                    padding: "8px 14px",
                    fontFamily: "var(--font-mono)",
                    fontSize: "13px",
                    textAlign: "right",
                    borderBottom: "1px solid var(--ink-faint)",
                    color: "var(--ink-medium)",
                  }}
                >
                  {fmt(row[def.key] as number)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
