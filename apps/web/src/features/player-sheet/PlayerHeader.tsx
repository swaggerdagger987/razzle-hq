"use client";

const POS_TOKEN: Record<string, string> = {
  QB: "var(--pos-qb)",
  RB: "var(--pos-rb)",
  WR: "var(--pos-wr)",
  TE: "var(--pos-te)",
};

type Props = {
  name: string;
  position: string;
  team: string | null;
};

export function PlayerHeader({ name, position, team }: Props) {
  const posColor = POS_TOKEN[position] ?? "var(--ink-light)";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "16px",
        flexWrap: "wrap",
      }}
    >
      <span
        style={{
          background: posColor,
          color: "var(--text-on-accent)",
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          fontWeight: 700,
          borderRadius: "var(--radius-sm)",
          padding: "4px 10px",
          display: "inline-block",
          border: "3px solid var(--ink)",
          boxShadow: "2px 2px 0 var(--ink)",
          letterSpacing: "0.06em",
          flexShrink: 0,
        }}
      >
        {position}
      </span>

      <h1
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "36px",
          margin: 0,
          lineHeight: 1.1,
          color: "var(--ink)",
        }}
      >
        {name}
      </h1>

      {team && (
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            color: "var(--ink-medium)",
            border: "2px solid var(--ink-faint)",
            borderRadius: "var(--radius-sm)",
            padding: "3px 8px",
            flexShrink: 0,
          }}
        >
          {team}
        </span>
      )}
    </div>
  );
}
