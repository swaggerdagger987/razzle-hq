const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type WeekStats = {
  week: number;
  pass_att: number;
  pass_cmp: number;
  pass_yd: number;
  pass_td: number;
  pass_int: number;
  pass_sack: number;
  pass_two_pt: number;
  rush_att: number;
  rush_yd: number;
  rush_td: number;
  rush_two_pt: number;
  target: number;
  rec: number;
  rec_yd: number;
  rec_td: number;
  rec_two_pt: number;
  fumble: number;
  fumble_lost: number;
  return_yd: number;
  return_td: number;
  special_teams_td: number;
  pat_made: number;
  pat_missed: number;
  fg_made: number;
  fg_missed: number;
};

export type PlayerSeason = {
  season: number;
  week_stats: WeekStats[];
};

export type PlayerDetail = {
  gsis_id: string;
  name: string;
  position: string;
  team: string | null;
  seasons: PlayerSeason[];
};

export type AdjacentPlayers = {
  prev_gsis_id: string | null;
  next_gsis_id: string | null;
};

export async function fetchPlayerDetail(gsis_id: string): Promise<PlayerDetail> {
  const url = `${API_URL}/api/players/${encodeURIComponent(gsis_id)}`;
  const response = await fetch(url);
  if (response.status === 404) {
    throw new Error("player not found");
  }
  if (!response.ok) {
    throw new Error(`player fetch failed: ${response.status}`);
  }
  return response.json() as Promise<PlayerDetail>;
}

export async function fetchAdjacentPlayers(
  gsis_id: string,
  season: number,
  position?: string,
): Promise<AdjacentPlayers> {
  const url = new URL(`${API_URL}/api/players/${encodeURIComponent(gsis_id)}/adjacent`);
  url.searchParams.set("season", String(season));
  if (position) url.searchParams.set("position", position);
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`adjacent fetch failed: ${response.status}`);
  }
  return response.json() as Promise<AdjacentPlayers>;
}
