"use client";

import { useQuery } from "@tanstack/react-query";
import { parseAsInteger, parseAsString, parseAsStringLiteral, useQueryStates } from "nuqs";
import { useEffect } from "react";
import { fetchScreener, type Position, type ScoringPreset } from "./api";
import { ScreenerTable } from "./ScreenerTable";

const PAGE_SIZE = 100;

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

const PRESET_LABEL_BY_VALUE: Record<ScoringPreset, string> = {
  standard: "Standard",
  PPR: "PPR",
  half: "Half",
  TEP: "TEP",
};

const EDITABLE_RULES = [
  { key: "pass_td", label: "Pass TD", step: 1, decimals: 0 },
  { key: "rush_td", label: "Rush TD", step: 1, decimals: 0 },
  { key: "rec_td", label: "Rec TD", step: 1, decimals: 0 },
  { key: "rec", label: "Rec", step: 0.5, decimals: 1 },
  { key: "rec_yd", label: "Rec yd/pt", step: 0.05, decimals: 2 },
  { key: "te_premium", label: "TE premium", step: 0.5, decimals: 1 },
] as const;

type EditableRuleKey = (typeof EDITABLE_RULES)[number]["key"];

const EDITABLE_KEYS = new Set<string>(EDITABLE_RULES.map((r) => r.key));

function buildDefaultsForPreset(preset: ScoringPreset): Record<EditableRuleKey, number> {
  const recByPreset: Record<ScoringPreset, number> = {
    standard: 0,
    PPR: 1,
    half: 0.5,
    TEP: 1,
  };
  const tepByPreset: Record<ScoringPreset, number> = {
    standard: 0,
    PPR: 0,
    half: 0,
    TEP: 0.5,
  };
  return {
    pass_td: 4,
    rush_td: 6,
    rec_td: 6,
    rec: recByPreset[preset],
    rec_yd: 0.1,
    te_premium: tepByPreset[preset],
  };
}

type ParsedRules =
  | { ok: true; rules: Record<EditableRuleKey, number> }
  | { ok: false; error: string };

function parseScoringRules(
  scoringRules: string,
  preset: ScoringPreset,
): ParsedRules {
  try {
    const parsed: unknown = JSON.parse(scoringRules);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return { ok: false, error: "This scoring link is invalid." };
    }
    const entries = Object.entries(parsed as Record<string, unknown>);
    const rules = buildDefaultsForPreset(preset);
    for (const [key, value] of entries) {
      if (!EDITABLE_KEYS.has(key)) {
        return { ok: false, error: "This scoring link is invalid." };
      }
      if (typeof value !== "number" || !Number.isFinite(value)) {
        return { ok: false, error: "This scoring link is invalid." };
      }
      rules[key as EditableRuleKey] = value;
    }
    return { ok: true, rules };
  } catch {
    return { ok: false, error: "This scoring link is invalid." };
  }
}

function rulesOverrideJson(overrides: Record<EditableRuleKey, number>): string {
  return JSON.stringify(overrides);
}

function formatRuleValue(value: number, decimals: number): string {
  if (decimals === 0) return String(value);
  return value.toFixed(decimals);
}

export function ScreenerPanel() {
  const [params, setParams] = useQueryStates({
    season: parseAsInteger.withDefault(2025),
    position: parseAsStringLiteral(POSITIONS),
    sort: parseAsStringLiteral(SORT_KEYS).withDefault("fantasy_points"),
    dir: parseAsStringLiteral(["asc", "desc"] as const).withDefault("desc"),
    page: parseAsInteger.withDefault(1),
    scoring_preset: parseAsString.withDefault("standard"),
    scoring_rules: parseAsString,
  });

  const { season, position, sort, dir, page, scoring_preset, scoring_rules } = params;

  const activePreset = (scoring_preset as ScoringPreset) ?? "standard";
  const presetLabel = PRESET_LABEL_BY_VALUE[activePreset] ?? "Standard";
  const rulesEditorOpen = scoring_rules != null;
  const parsedRules = scoring_rules != null ? parseScoringRules(scoring_rules, activePreset) : null;
  const rulesValid = parsedRules?.ok === true;
  const editorRules = rulesValid ? parsedRules.rules : null;

  // Scoring state is exactly URL-carried (invalid links stay fail-closed via API).
  const effectiveScoringRules = scoring_rules;

  const safePage = Math.max(1, page);
  const offset = (safePage - 1) * PAGE_SIZE;

  const { data, isPending, isError } = useQuery({
    queryKey: [
      "screener",
      season,
      position,
      sort,
      dir,
      safePage,
      scoring_preset,
      effectiveScoringRules,
    ],
    queryFn: () =>
      fetchScreener({
        season,
        position: position as Position | null,
        sort,
        dir: dir as "asc" | "desc",
        limit: PAGE_SIZE,
        offset,
        scoring_preset: activePreset,
        scoring_rules: effectiveScoringRules,
      }),
  });

  // Normalize page without looping: clamp <1 to 1; past end → page 1.
  useEffect(() => {
    if (page < 1) {
      void setParams({ page: 1 });
      return;
    }
    if (data && data.total > 0) {
      const maxPage = Math.ceil(data.total / PAGE_SIZE);
      if (page > maxPage) {
        void setParams({ page: 1 });
      }
    }
  }, [page, data, setParams]);

  function handleSortChange(key: string, nextDir: "asc" | "desc") {
    void setParams({ sort: key as SortKey, dir: nextDir, page: 1 });
  }

  function handlePositionClick(pos: Position) {
    void setParams({ position: position === pos ? null : pos, page: 1 });
  }

  function handlePresetClick(preset: ScoringPreset) {
    void setParams({ scoring_preset: preset, scoring_rules: null });
  }

  function handleRuleChange(key: EditableRuleKey, delta: number) {
    if (!editorRules) return;
    const rule = EDITABLE_RULES.find((r) => r.key === key);
    if (!rule) return;
    const next = Math.round((editorRules[key] + delta * rule.step) * 100) / 100;
    const updated = { ...editorRules, [key]: Math.max(0, next) };
    void setParams({ scoring_rules: rulesOverrideJson(updated) });
  }

  function toggleEditor() {
    if (rulesEditorOpen) {
      void setParams({ scoring_rules: null });
      return;
    }
    void setParams({
      scoring_rules: rulesOverrideJson(buildDefaultsForPreset(activePreset)),
    });
  }

  const total = data?.total ?? 0;
  const maxPage = total > 0 ? Math.ceil(total / PAGE_SIZE) : 1;
  const rangeStart = total === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const rangeEnd = total === 0 ? 0 : Math.min(safePage * PAGE_SIZE, total);
  const canPrev = safePage > 1;
  const canNext = total > 0 && safePage < maxPage;
  const rangeLabel =
    total === 0
      ? `0 of 0 players · ${season}`
      : `${rangeStart}–${rangeEnd} of ${total} players · ${season}`;

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
          {data ? rangeLabel : null}
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
          const isActive = scoring_preset === value;
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
            flexDirection: "column",
            gap: "14px",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              color: "var(--ink-medium)",
            }}
          >
            Custom overrides · {presetLabel} base
          </span>

          {parsedRules && !parsedRules.ok && (
            <p
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                color: "var(--red)",
                margin: 0,
              }}
            >
              {parsedRules.error}
            </p>
          )}

          {editorRules && (
            <div
              style={{
                display: "flex",
                gap: "24px",
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              {EDITABLE_RULES.map((rule) => {
                const value = editorRules[rule.key];
                return (
                  <div
                    key={rule.key}
                    style={{ display: "flex", flexDirection: "column", gap: "6px" }}
                  >
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
                        {formatRuleValue(value, rule.decimals)}
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
            </div>
          )}
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
          running the numbers...
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

      {data && data.rows.length === 0 && !isPending && !isError && (
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
        <>
          <ScreenerTable
            rows={data.rows}
            sortKey={sort}
            sortDir={dir as "asc" | "desc"}
            scoringPreset={activePreset}
            scoringRules={effectiveScoringRules}
            onSortChange={handleSortChange}
          />

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              flexWrap: "wrap",
              marginTop: "16px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "12px",
                color: "var(--ink-light)",
              }}
            >
              {rangeLabel}
            </span>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <button
                className="btn-chunky"
                disabled={!canPrev}
                onClick={() => void setParams({ page: safePage - 1 })}
                style={{
                  opacity: canPrev ? 1 : 0.35,
                  cursor: canPrev ? "pointer" : "default",
                  fontSize: "13px",
                  padding: "6px 14px",
                }}
                aria-label="Previous page"
              >
                ← Prev
              </button>
              <button
                className="btn-chunky"
                disabled={!canNext}
                onClick={() => void setParams({ page: safePage + 1 })}
                style={{
                  opacity: canNext ? 1 : 0.35,
                  cursor: canNext ? "pointer" : "default",
                  fontSize: "13px",
                  padding: "6px 14px",
                }}
                aria-label="Next page"
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
