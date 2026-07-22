"use client";

import { useQuery } from "@tanstack/react-query";
import { parseAsInteger, parseAsString, parseAsStringLiteral, useQueryStates } from "nuqs";
import { fetchScreener, type Position, type ScoringPreset } from "./api";
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
  "fantasy_points",
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

const PRESET_LABELS: { value: ScoringPreset; label: string }[] = [
  { value: "standard", label: "Standard" },
  { value: "PPR", label: "PPR" },
  { value: "half", label: "Half" },
  { value: "TEP", label: "TEP" },
];

const EDITABLE_RULES = [
  { key: "pass_td", label: "Pass TD", defaultValue: 4 },
  { key: "rush_td", label: "Rush TD", defaultValue: 6 },
  { key: "rec_td", label: "Rec TD", defaultValue: 6 },
  { key: "rec_yd", label: "Rec yd/pt", defaultValue: 0.1 },
] as const;

type EditableRuleKey = (typeof EDITABLE_RULES)[number]["key"];

function buildDefaultRules(): Record<EditableRuleKey, number> {
  return Object.fromEntries(EDITABLE_RULES.map((r) => [r.key, r.defaultValue])) as Record<
    EditableRuleKey,
    number
  >;
}

function rulesFromUrl(scoringRules: string | null): Record<EditableRuleKey, number> {
  const defaults = buildDefaultRules();
  if (!scoringRules) return defaults;
  try {
    const parsed = JSON.parse(scoringRules) as Partial<Record<EditableRuleKey, number>>;
    return { ...defaults, ...parsed };
  } catch {
    return defaults;
  }
}

function rulesOverrideJson(overrides: Record<EditableRuleKey, number>): string {
  return JSON.stringify(overrides);
}

export function ScreenerPanel() {
  const [params, setParams] = useQueryStates({
    season: parseAsInteger.withDefault(2025),
    position: parseAsStringLiteral(POSITIONS),
    sort: parseAsStringLiteral(SORT_KEYS).withDefault("name"),
    dir: parseAsStringLiteral(["asc", "desc"] as const).withDefault("asc"),
    scoring_preset: parseAsString.withDefault("standard"),
    scoring_rules: parseAsString,
  });

  const { season, position, sort, dir, scoring_preset, scoring_rules } = params;

  // Scoring state is exactly URL-carried.
  const effectiveScoringRules = scoring_rules;
  const editorRules = rulesFromUrl(scoring_rules);
  const rulesEditorOpen = scoring_rules != null;
  const activePreset = (scoring_preset as ScoringPreset) ?? "standard";

  const { data, isPending, isError } = useQuery({
    queryKey: ["screener", season, position, sort, dir, scoring_preset, effectiveScoringRules],
    queryFn: () =>
      fetchScreener({
        season,
        position: position as Position | null,
        sort,
        dir: dir as "asc" | "desc",
        limit: 100,
        offset: 0,
        scoring_preset: activePreset,
        scoring_rules: effectiveScoringRules,
      }),
  });

  function handleSortChange(key: string, nextDir: "asc" | "desc") {
    void setParams({ sort: key as SortKey, dir: nextDir });
  }

  function handlePositionClick(pos: Position) {
    void setParams({ position: position === pos ? null : pos });
  }

  function handlePresetClick(preset: ScoringPreset) {
    void setParams({ scoring_preset: preset, scoring_rules: null });
  }

  function handleRuleChange(key: EditableRuleKey, delta: number) {
    const step = key === "rec_yd" ? 0.05 : 1;
    const next = Math.round((editorRules[key] + delta * step) * 100) / 100;
    const updated = { ...editorRules, [key]: Math.max(0, next) };
    void setParams({ scoring_rules: rulesOverrideJson(updated) });
  }

  function toggleEditor() {
    if (rulesEditorOpen) {
      void setParams({ scoring_rules: null });
      return;
    }
    void setParams({ scoring_rules: rulesOverrideJson(buildDefaultRules()) });
  }

  return (
    <section
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "32px 24px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          flexWrap: "wrap",
          marginBottom: "16px",
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
          Scratchpad
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

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          flexWrap: "wrap",
          marginBottom: rulesEditorOpen ? "12px" : "20px",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "11px",
            color: "var(--ink-light)",
            marginRight: "4px",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Scoring
        </span>

        {PRESET_LABELS.map(({ value, label }) => {
          const isActive = scoring_preset === value && !rulesEditorOpen;
          return (
            <button
              key={value}
              onClick={() => handlePresetClick(value)}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                padding: "4px 12px",
                border: "3px solid var(--ink)",
                borderRadius: "var(--radius-sm)",
                cursor: "pointer",
                background: isActive ? "var(--orange)" : "var(--bg-card)",
                color: isActive ? "var(--text-on-accent)" : "var(--ink)",
                fontWeight: isActive ? 700 : 400,
                boxShadow: isActive ? "2px 2px 0 var(--ink)" : "none",
                transition: "background 0.1s, color 0.1s",
              }}
            >
              {label}
            </button>
          );
        })}

        <button
          onClick={toggleEditor}
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            padding: "4px 12px",
            border: "3px solid var(--ink)",
            borderRadius: "var(--radius-sm)",
            cursor: "pointer",
            background: rulesEditorOpen ? "var(--ink)" : "var(--bg-card)",
            color: rulesEditorOpen ? "var(--bg)" : "var(--ink)",
            boxShadow: rulesEditorOpen ? "2px 2px 0 var(--orange)" : "none",
            transition: "background 0.1s, color 0.1s",
            marginLeft: "4px",
          }}
        >
          Custom
        </button>
      </div>

      {rulesEditorOpen && (
        <div
          className="card-chunky"
          style={{
            padding: "16px 20px",
            marginBottom: "20px",
            display: "flex",
            gap: "24px",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          {EDITABLE_RULES.map((rule) => {
            const value = editorRules[rule.key];
            const isYdPt = rule.key === "rec_yd";
            return (
              <div key={rule.key} style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "10px",
                    textTransform: "uppercase",
                    color: "var(--ink-light)",
                    letterSpacing: "0.06em",
                  }}
                >
                  {rule.label}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <button
                    onClick={() => handleRuleChange(rule.key, -1)}
                    style={{
                      width: "28px",
                      height: "28px",
                      border: "2px solid var(--ink)",
                      borderRadius: "var(--radius-sm)",
                      cursor: "pointer",
                      background: "var(--bg-card)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "16px",
                      lineHeight: 1,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    −
                  </button>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "16px",
                      fontWeight: 700,
                      minWidth: "40px",
                      textAlign: "center",
                      color: "var(--ink)",
                    }}
                  >
                    {isYdPt ? value.toFixed(2) : value}
                  </span>
                  <button
                    onClick={() => handleRuleChange(rule.key, 1)}
                    style={{
                      width: "28px",
                      height: "28px",
                      border: "2px solid var(--ink)",
                      borderRadius: "var(--radius-sm)",
                      cursor: "pointer",
                      background: "var(--bg-card)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "16px",
                      lineHeight: 1,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    +
                  </button>
                </div>
              </div>
            );
          })}

          <span
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "13px",
              color: "var(--ink-light)",
              marginLeft: "auto",
            }}
          >
            calculating your league&apos;s points...
          </span>
        </div>
      )}

      {isPending && (
        <p
          style={{
            fontFamily: "var(--font-hand)",
            fontSize: "24px",
            color: "var(--ink-light)",
            padding: "48px 0",
          }}
        >
          {rulesEditorOpen ? "calculating your league’s points..." : "pulling film..."}
        </p>
      )}

      {isError && !isPending && (
        <div className="card-chunky" style={{ padding: "32px", textAlign: "center" }}>
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
        <div className="card-chunky" style={{ padding: "32px", textAlign: "center" }}>
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
          scoringPreset={activePreset}
          scoringRules={effectiveScoringRules}
          onSortChange={handleSortChange}
        />
      )}
    </section>
  );
}
