"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useMemo } from "react";
import type { ScreenerRow } from "./api";

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

const ALL_COLUMNS = [
  helper.accessor("name", {
    id: "name",
    header: "Player",
    enableSorting: true,
    cell: (info) => (
      <span style={{ fontFamily: "var(--font-display)", fontSize: "14px" }}>
        {info.getValue()}
      </span>
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
];

type Props = {
  rows: ScreenerRow[];
  sortKey: string;
  sortDir: "asc" | "desc";
  onSortChange: (key: string, dir: "asc" | "desc") => void;
};

export function ScreenerTable({ rows, sortKey, sortDir, onSortChange }: Props) {
  const columns = useMemo(() => ALL_COLUMNS, []);

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
      const next =
        typeof updater === "function" ? updater(sorting) : updater;
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
                    color: isSorted ? "var(--orange)" : "var(--ink)",
                    borderBottom: "3px solid var(--ink)",
                    whiteSpace: "nowrap",
                    background: isSorted
                      ? "rgba(var(--sort-highlight), 0.12)"
                      : undefined,
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
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  style={{
                    padding: "8px 12px",
                    fontFamily: "var(--font-mono)",
                    fontSize: "13px",
                    textAlign: cell.column.id === "name" ? "left" : "right",
                    borderBottom: "1px solid var(--ink-faint)",
                    color: "var(--ink-medium)",
                  }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
