"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import Link from "next/link";
import { useMemo } from "react";
import type { ScreenerRow, ScoringPreset } from "./api";
import { playerHref } from "./scoring-url";

const POS_TOKEN: Record<string, string> = {
  QB: "var(--pos-qb)",
  RB: "var(--pos-rb)",
  WR: "var(--pos-wr)",
  TE: "var(--pos-te)",
};

const helper = createColumnHelper<ScreenerRow>();

function numCol(key: keyof ScreenerRow, header: string, decimals = 0) {
  return helper.accessor(key, {
    id: key,
    header,
    cell: (info) => {
      const v = info.getValue();
      if (v == null) return "—";
      const n = Number(v);
      return decimals > 0 ? n.toFixed(decimals) : String(Math.round(n));
    },
    enableSorting: true,
  });
}

function buildColumns(scoringPreset: ScoringPreset, scoringRules: string | null) {
  return [
    helper.accessor("name", {
      id: "name",
      header: "Player",
      enableSorting: true,
      cell: (info) => (
        <Link
          href={playerHref(info.row.original.gsis_id, {
            scoring_preset: scoringPreset,
            scoring_rules: scoringRules,
          })}
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            color: "var(--ink)",
            textDecoration: "none",
          }}
        >
          {info.getValue()}
        </Link>
      ),
    }),
    helper.accessor("position", {
      id: "position",
      header: "Pos",
      enableSorting: false,
      cell: (info) => {
        const pos = info.getValue();
        return (
          <span
            style={{
              background: POS_TOKEN[pos] ?? "var(--ink-light)",
              color: "var(--text-on-accent)",
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              fontWeight: 700,
              borderRadius: "var(--radius-sm)",
              padding: "2px 7px",
              display: "inline-block",
              border: "2px solid var(--ink)",
            }}
          >
            {pos}
          </span>
        );
      },
    }),
    helper.accessor("team", {
      id: "team",
      header: "Team",
      enableSorting: false,
      cell: (info) => info.getValue() ?? "—",
    }),
    numCol("games", "G"),
    numCol("pass_att", "Att"),
    numCol("pass_yd", "PaYd"),
    numCol("pass_td", "PaTD"),
    numCol("pass_int", "INT"),
    numCol("rush_att", "Car"),
    numCol("rush_yd", "RuYd"),
    numCol("rush_td", "RuTD"),
    numCol("target", "Tgt"),
    numCol("rec", "Rec"),
    numCol("rec_yd", "ReYd"),
    numCol("rec_td", "ReTD"),
    numCol("fumble_lost", "FL"),
    helper.accessor("fantasy_points", {
      id: "fantasy_points",
      header: "Pts",
      enableSorting: true,
      cell: (info) => {
        const v = info.getValue();
        if (v == null) return "—";
        return Number(v).toFixed(1);
      },
    }),
  ];
}

type Props = {
  rows: ScreenerRow[];
  sortKey: string;
  sortDir: "asc" | "desc";
  scoringPreset?: ScoringPreset;
  scoringRules?: string | null;
  onSortChange: (key: string, dir: "asc" | "desc") => void;
};

export function ScreenerTable({
  rows,
  sortKey,
  sortDir,
  scoringPreset = "standard",
  scoringRules = null,
  onSortChange,
}: Props) {
  const columns = useMemo(
    () => buildColumns(scoringPreset, scoringRules),
    [scoringPreset, scoringRules],
  );

  const sorting: SortingState = useMemo(
    () => [{ id: sortKey, desc: sortDir === "desc" }],
    [sortKey, sortDir],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    manualSorting: true,
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      if (next.length > 0) {
        onSortChange(next[0].id, next[0].desc ? "desc" : "asc");
      }
    },
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.gsis_id,
  });

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
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--bg-warm)" }}>
            {table.getHeaderGroups()[0]?.headers.map((header) => {
              const isSorted = header.column.getIsSorted();
              const canSort = header.column.getCanSort();
              const isFpCol = header.id === "fantasy_points";
              return (
                <th
                  key={header.id}
                  onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                  style={{
                    padding: "10px 12px",
                    fontFamily: "var(--font-display)",
                    fontSize: "11px",
                    textTransform: "uppercase",
                    textAlign: header.id === "name" ? "left" : "right",
                    cursor: canSort ? "pointer" : "default",
                    userSelect: "none",
                    color: isSorted ? "var(--orange)" : isFpCol ? "var(--orange)" : "var(--ink)",
                    borderBottom: "3px solid var(--ink)",
                    borderLeft: isFpCol ? "2px solid var(--ink-faint)" : undefined,
                    whiteSpace: "nowrap",
                    background: isSorted ? "rgba(var(--sort-highlight), 0.12)" : undefined,
                  }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {isSorted ? (isSorted === "desc" ? " ↓" : " ↑") : ""}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row, idx) => (
            <tr
              key={row.id}
              style={{
                background: idx % 2 === 1 ? "var(--zebra-stripe)" : undefined,
              }}
            >
              {row.getVisibleCells().map((cell) => {
                const isFpCell = cell.column.id === "fantasy_points";
                return (
                  <td
                    key={cell.id}
                    style={{
                      padding: "8px 12px",
                      fontFamily: "var(--font-mono)",
                      fontSize: "13px",
                      textAlign: cell.column.id === "name" ? "left" : "right",
                      borderBottom: "1px solid var(--ink-faint)",
                      borderLeft: isFpCell ? "2px solid var(--ink-faint)" : undefined,
                      color: isFpCell ? "var(--ink)" : "var(--ink-medium)",
                      fontWeight: isFpCell ? 600 : undefined,
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
