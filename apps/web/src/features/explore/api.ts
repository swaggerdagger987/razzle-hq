const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Position = "QB" | "RB" | "WR" | "TE";

export type ScoringPreset = "standard" | "PPR" | "half" | "TEP";

export type ScreenerRow = {
  gsis_id: string;
  name: string;
  position: Position;
  team: string | null;
  games: number;
  pass_att: number;
  pass_cmp: number;
  pass_yd: number;
  pass_td: number;
  pass_int: number;
  rush_att: number;
  rush_yd: number;
  rush_td: number;
  target: number;
  rec: number;
  rec_yd: number;
  rec_td: number;
  fumble_lost: number;
  fantasy_points: number;
};

export type ScreenerResponse = {
  season: number;
  total: number;
  rows: ScreenerRow[];
};

export type ScreenerParams = {
  season: number;
  position: Position | null;
  sort: string;
  dir: "asc" | "desc";
  limit: number;
  offset: number;
  scoring_preset?: ScoringPreset;
  scoring_rules?: string | null;
};

export async function fetchScreener(params: ScreenerParams): Promise<ScreenerResponse> {
  const url = new URL(`${API_URL}/api/screener`);
  url.searchParams.set("season", String(params.season));
  if (params.position) url.searchParams.set("position", params.position);
  url.searchParams.set("sort", params.sort);
  url.searchParams.set("dir", params.dir);
  url.searchParams.set("limit", String(params.limit));
  url.searchParams.set("offset", String(params.offset));
  if (params.scoring_preset) url.searchParams.set("scoring_preset", params.scoring_preset);
  if (params.scoring_rules) url.searchParams.set("scoring_rules", params.scoring_rules);

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`screener fetch failed: ${response.status}`);
  }
  return response.json() as Promise<ScreenerResponse>;
}
