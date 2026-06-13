const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Position = "QB" | "RB" | "WR" | "TE";

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
};

export async function fetchScreener(params: ScreenerParams): Promise<ScreenerResponse> {
  const url = new URL(`${API_URL}/api/screener`);
  url.searchParams.set("season", String(params.season));
  if (params.position) url.searchParams.set("position", params.position);
  url.searchParams.set("sort", params.sort);
  url.searchParams.set("dir", params.dir);
  url.searchParams.set("limit", String(params.limit));
  url.searchParams.set("offset", String(params.offset));

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`screener fetch failed: ${response.status}`);
  }
  return response.json() as Promise<ScreenerResponse>;
}
