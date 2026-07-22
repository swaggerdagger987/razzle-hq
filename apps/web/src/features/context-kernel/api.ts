const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export type UserIdentity = {
  user_id: string;
  username: string;
  display_name?: string | null;
  avatar?: string | null;
};

export type LeagueSummary = {
  league_id: string;
  name: string;
  season: number;
  sport?: string;
  total_rosters?: number | null;
};

export type UnsupportedKey = {
  key: string;
  value: boolean | number | string | null;
  reason: string;
};

export type CoverageReport = {
  status: "full" | "partial";
  supported_keys: string[];
  unsupported_keys: UnsupportedKey[];
  ignored_zero_keys: string[];
};

export type CompiledRules = {
  league_id: string;
  name: string;
  season: string;
  league: {
    format?: string;
    playoff_teams?: number;
    playoff_start_week?: number;
    scoring?: {
      receiving?: {
        te_premium?: number;
      };
    };
  };
  matchup: {
    style: "h2h" | "h2h_median";
    median_enabled?: boolean;
  };
  te_premium: boolean;
  superflex: boolean;
  best_ball?: boolean;
  coverage: CoverageReport;
};

export type ProvenanceSource = {
  name: string;
  as_of: string;
  version?: string | null;
};

export type ProvenanceMeta = {
  revision?: string | null;
  sources: ProvenanceSource[];
  coverage?: CoverageReport | null;
  assumptions?: string[];
  model_version?: string | null;
};

export type ConnectResponse = {
  user: UserIdentity;
  season: number;
  leagues: LeagueSummary[];
  meta: ProvenanceMeta;
};

export type ContextRevisionResponse = {
  revision_id: string;
  league_id: string;
  season: number;
  created_at: string;
  league: Record<string, unknown>;
  users: Record<string, unknown>[];
  rosters: Record<string, unknown>[];
  matchups_by_week: Record<string, unknown>;
  transactions_by_week: Record<string, unknown>;
  traded_picks: Record<string, unknown>[];
  state: Record<string, unknown>;
  compiled_rules: CompiledRules;
  coverage: CoverageReport;
  meta: ProvenanceMeta;
};

function detailFromBody(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.length > 0) return detail;
    if (Array.isArray(detail)) {
      try {
        return JSON.stringify(detail);
      } catch {
        return fallback;
      }
    }
  }
  return fallback;
}

async function readJsonBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  const body = await readJsonBody(response);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      detailFromBody(body, `request failed: ${response.status}`),
    );
  }
  return body as T;
}

export function connectContext(username: string): Promise<ConnectResponse> {
  return requestJson<ConnectResponse>("/api/context/connect", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username }),
  });
}

export function refreshLeague(
  leagueId: string,
  username: string,
): Promise<ContextRevisionResponse> {
  return requestJson<ContextRevisionResponse>(
    `/api/context/leagues/${encodeURIComponent(leagueId)}/refresh`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username }),
    },
  );
}

export function fetchRevision(revisionId: string): Promise<ContextRevisionResponse> {
  return requestJson<ContextRevisionResponse>(
    `/api/context/revision/${encodeURIComponent(revisionId)}`,
  );
}
