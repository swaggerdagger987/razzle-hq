/** Pure helpers for encoding scoring state into URL query strings. */

export type ScoringUrlState = {
  scoring_preset?: string | null;
  scoring_rules?: string | null;
};

export function buildScoringSearchParams(state: ScoringUrlState = {}): URLSearchParams {
  const params = new URLSearchParams();
  params.set("scoring_preset", state.scoring_preset ?? "standard");
  if (state.scoring_rules) {
    params.set("scoring_rules", state.scoring_rules);
  }
  return params;
}

export function scoringQueryString(state: ScoringUrlState = {}): string {
  const qs = buildScoringSearchParams(state).toString();
  return qs ? `?${qs}` : "";
}

export function playerHref(gsisId: string, state: ScoringUrlState = {}): string {
  return `/player/${encodeURIComponent(gsisId)}${scoringQueryString(state)}`;
}

export function scratchpadHref(state: ScoringUrlState = {}): string {
  return `/scratchpad${scoringQueryString(state)}`;
}
