"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { parseAsString, useQueryStates } from "nuqs";
import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import {
  ApiError,
  connectContext,
  fetchRevision,
  refreshLeague,
  type CompiledRules,
  type ContextRevisionResponse,
  type CoverageReport,
  type LeagueSummary,
  type MatchupStyle,
} from "./api";

function formatLabel(format: CompiledRules["league"]["format"] | undefined): string {
  if (!format) return "—";
  return format.replace(/_/g, " ");
}

function matchupLabel(style: MatchupStyle | undefined): string {
  if (style === "h2h_median") return "H2H + median";
  if (style === "h2h") return "H2H";
  return "—";
}

function tePremiumLabel(rules: CompiledRules): string {
  if (!rules.te_premium) return "none";
  const value = rules.league.scoring.receiving.te_premium;
  if (typeof value === "number") return String(value);
  return "yes";
}

function coverageFromRevision(revision: ContextRevisionResponse): CoverageReport {
  return revision.coverage ?? revision.compiled_rules.coverage;
}

function stringField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function numberField(record: Record<string, unknown>, key: string): number | null {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function errorVoice(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return error.detail || "That handle isn't on the board.";
    }
    if (error.status === 403) {
      return error.detail || "That league isn't yours to pull.";
    }
    if (error.status === 502) {
      return error.detail || "Sleeper's tape went dark upstream. Try again in a beat.";
    }
    return error.detail || `Request failed (${error.status}).`;
  }
  if (error instanceof Error && error.message) return error.message;
  return "Something went sideways checking the tape.";
}

function formatAsOf(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function disabledControlStyle(disabled: boolean): CSSProperties {
  if (!disabled) return {};
  return {
    opacity: 0.55,
    cursor: "not-allowed",
    transform: "none",
    boxShadow: "none",
    pointerEvents: "none",
  };
}

export function ContextKernelDemo() {
  const queryClient = useQueryClient();
  const [params, setParams] = useQueryStates({
    username: parseAsString,
    league_id: parseAsString,
    revision: parseAsString,
  });

  const { username, league_id, revision } = params;
  const [draftUsername, setDraftUsername] = useState(username ?? "");

  useEffect(() => {
    setDraftUsername(username ?? "");
  }, [username]);

  const connectEnabled = Boolean(username) && !revision;

  const connectQuery = useQuery({
    queryKey: ["context-connect", username],
    queryFn: () => connectContext(username!),
    enabled: connectEnabled,
    retry: false,
  });

  const revisionQuery = useQuery({
    queryKey: ["context-revision", revision],
    queryFn: () => fetchRevision(revision!),
    enabled: Boolean(revision),
    retry: false,
  });

  useEffect(() => {
    if (revisionQuery.data && !league_id) {
      void setParams({ league_id: revisionQuery.data.league_id });
    }
  }, [revisionQuery.data, league_id, setParams]);

  const refreshMutation = useMutation({
    mutationFn: ({ leagueId, user }: { leagueId: string; user: string }) =>
      refreshLeague(leagueId, user),
    onSuccess: async (data) => {
      queryClient.setQueryData(["context-revision", data.revision_id], data);
      await setParams({
        league_id: data.league_id,
        revision: data.revision_id,
      });
    },
  });

  async function onSubmitUsername(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = draftUsername.trim();
    if (!next) return;
    refreshMutation.reset();
    // Clear league/revision first so reload-GET law re-enables connect.
    await setParams({
      username: next,
      league_id: null,
      revision: null,
    });
    // Same-username retry: invalidate so a prior 404/502 is not a stale no-op.
    await queryClient.invalidateQueries({ queryKey: ["context-connect", next] });
  }

  async function onChooseLeague(league: LeagueSummary) {
    if (!username) return;
    refreshMutation.reset();
    await setParams({ league_id: league.league_id, revision: null });
    refreshMutation.mutate({ leagueId: league.league_id, user: username });
  }

  function onPullFresh() {
    if (!username || !league_id) return;
    refreshMutation.mutate({ leagueId: league_id, user: username });
  }

  const leagues = connectEnabled ? (connectQuery.data?.leagues ?? []) : [];
  const connectPending = connectEnabled && connectQuery.isFetching;
  const connectError =
    connectEnabled && connectQuery.isError ? errorVoice(connectQuery.error) : null;
  const refreshPending = refreshMutation.isPending;
  const refreshError = refreshMutation.isError
    ? errorVoice(refreshMutation.error)
    : null;
  const revisionPending = Boolean(revision) && revisionQuery.isFetching;
  const revisionError = revisionQuery.isError ? errorVoice(revisionQuery.error) : null;
  const revisionData = revisionQuery.data ?? null;
  const canPullFresh = Boolean(username && league_id) && !refreshPending;

  // With a revision in URL, ignore stale connect errors; revision GET is critical.
  // Refresh errors still surface (choose league / pull fresh).
  const criticalError = revision
    ? revisionError || refreshError
    : refreshError || connectError;
  const loadingStatus =
    connectPending || refreshPending || revisionPending ? "checking the tape..." : null;

  const connectDisabled = !draftUsername.trim() || connectPending || refreshPending;
  const showEmptyLeagues =
    connectEnabled &&
    !connectPending &&
    connectQuery.isSuccess &&
    leagues.length === 0;

  return (
    <div
      style={{
        maxWidth: "960px",
        margin: "0 auto",
        padding: "24px 16px 64px",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
      }}
    >
      <header style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <h1
          className="font-display"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(2.5rem, 8vw, 3.75rem)",
            lineHeight: 1.05,
            color: "var(--ink)",
            margin: 0,
          }}
        >
          Connect Sleeper
        </h1>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "15px",
            lineHeight: 1.5,
            color: "var(--ink-medium)",
            margin: 0,
            maxWidth: "42rem",
          }}
        >
          Pull scoring, rosters, and league truth for the leagues you own — nothing else.
        </p>
      </header>

      <form
        onSubmit={onSubmitUsername}
        className="card-chunky"
        style={{
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <label
          htmlFor="sleeper-username"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14px",
            textTransform: "uppercase",
            color: "var(--ink)",
          }}
        >
          Sleeper username
        </label>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "12px",
            alignItems: "stretch",
          }}
        >
          <input
            id="sleeper-username"
            name="username"
            type="text"
            autoComplete="username"
            value={draftUsername}
            onChange={(event) => setDraftUsername(event.target.value)}
            placeholder="your sleeper handle"
            disabled={connectPending || refreshPending}
            style={{
              flex: "1 1 220px",
              minWidth: 0,
              border: "3px solid var(--ink)",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg)",
              color: "var(--ink)",
              fontFamily: "var(--font-mono)",
              fontSize: "16px",
              padding: "12px 14px",
            }}
          />
          <button
            type="submit"
            className="btn-chunky"
            data-active={connectDisabled ? undefined : "true"}
            disabled={connectDisabled}
            style={{
              flex: "0 0 auto",
              ...disabledControlStyle(connectDisabled),
            }}
          >
            {connectPending ? "checking the tape..." : "Connect"}
          </button>
        </div>
      </form>

      {loadingStatus ? (
        <p
          aria-live="polite"
          style={{
            fontFamily: "var(--font-hand)",
            fontSize: "22px",
            color: "var(--ink-light)",
            margin: 0,
            minHeight: "1.5rem",
          }}
        >
          {loadingStatus}
        </p>
      ) : null}

      {criticalError ? (
        <div
          className="card-chunky"
          role="alert"
          aria-live="assertive"
          style={{
            padding: "16px 18px",
            background: "var(--red-light)",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "14px",
              lineHeight: 1.45,
              color: "var(--ink)",
              margin: 0,
            }}
          >
            {criticalError}
          </p>
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "20px",
              color: "var(--ink-medium)",
              margin: 0,
            }}
          >
            ball up top — try again when the tape clears
          </p>
        </div>
      ) : null}

      {showEmptyLeagues ? (
        <div
          className="card-chunky"
          style={{ padding: "28px 20px", textAlign: "center" }}
          role="status"
        >
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "26px",
              color: "var(--ink-medium)",
              margin: 0,
            }}
          >
            No leagues on the board for this handle.
          </p>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "13px",
              color: "var(--ink-light)",
              marginTop: "8px",
            }}
          >
            Check the spelling, or try again once the season tape is up.
          </p>
        </div>
      ) : null}

      {leagues.length > 0 ? (
        <section style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "18px",
              textTransform: "uppercase",
              margin: 0,
              color: "var(--ink)",
            }}
          >
            Your leagues
            {connectQuery.data ? ` · ${connectQuery.data.season}` : ""}
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
              gap: "16px",
            }}
          >
            {leagues.map((league) => {
              const selected = league_id === league.league_id;
              const chooseDisabled = refreshPending || !username;
              const choosing =
                refreshPending && league_id === league.league_id && !revision;
              return (
                <article
                  key={league.league_id}
                  className="card-chunky"
                  style={{
                    padding: "16px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "10px",
                    outline: selected ? "3px solid var(--orange)" : undefined,
                    outlineOffset: selected ? "2px" : undefined,
                  }}
                >
                  <div>
                    <p
                      style={{
                        fontFamily: "var(--font-display)",
                        fontSize: "18px",
                        margin: 0,
                        color: "var(--ink)",
                        lineHeight: 1.2,
                      }}
                    >
                      {league.name}
                    </p>
                    <p
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "12px",
                        color: "var(--ink-light)",
                        margin: "6px 0 0",
                      }}
                    >
                      Season {league.season}
                      {typeof league.total_rosters === "number"
                        ? ` · ${league.total_rosters} teams`
                        : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn-chunky"
                    data-active={selected && !chooseDisabled ? "true" : undefined}
                    aria-pressed={selected}
                    disabled={chooseDisabled}
                    onClick={() => void onChooseLeague(league)}
                    style={{
                      marginTop: "auto",
                      ...disabledControlStyle(chooseDisabled),
                    }}
                  >
                    {choosing ? "checking the tape..." : selected ? "Selected" : "Choose"}
                  </button>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {revisionPending && !revisionData ? (
        <div className="card-chunky" style={{ padding: "28px 20px" }} role="status">
          <p
            style={{
              fontFamily: "var(--font-hand)",
              fontSize: "24px",
              color: "var(--ink-light)",
              margin: 0,
            }}
          >
            checking the tape...
          </p>
        </div>
      ) : null}

      {revisionData ? (
        <RevisionCard
          revision={revisionData}
          canPullFresh={canPullFresh}
          pullPending={refreshPending}
          onPullFresh={onPullFresh}
        />
      ) : null}
    </div>
  );
}

function RevisionCard({
  revision,
  canPullFresh,
  pullPending,
  onPullFresh,
}: {
  revision: ContextRevisionResponse;
  canPullFresh: boolean;
  pullPending: boolean;
  onPullFresh: () => void;
}) {
  const rules = revision.compiled_rules;
  const coverage = coverageFromRevision(revision);
  const leagueName =
    rules.name ||
    stringField(revision.league, "name") ||
    `League ${revision.league_id}`;
  const seasonLabel = rules.season || String(revision.season);
  const format = formatLabel(rules.league.format);
  const status = stringField(revision.league, "status");
  const teamCount = numberField(revision.league, "total_rosters");
  const playoffTeams = rules.league.playoff_teams;
  const playoffStart = rules.league.playoff_start_week;
  const isPartial = coverage.status === "partial";
  const scratchpadHref = `/scratchpad?revision=${encodeURIComponent(revision.revision_id)}`;
  const pullDisabled = !canPullFresh;

  return (
    <section
      className="card-chunky"
      style={{
        position: "relative",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        overflow: "hidden",
      }}
      aria-label="League context revision"
    >
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          right: "16px",
          bottom: "12px",
          fontFamily: "var(--font-hand)",
          fontSize: "22px",
          color: "var(--ink-faint)",
          opacity: 0.55,
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        razzle.lol
      </span>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <p
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "12px",
              textTransform: "uppercase",
              color: "var(--ink-light)",
              margin: 0,
            }}
          >
            Revision case
          </p>
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "28px",
              margin: "4px 0 0",
              color: "var(--ink)",
              lineHeight: 1.1,
            }}
          >
            {leagueName}
          </h2>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "13px",
              color: "var(--ink-medium)",
              margin: "8px 0 0",
            }}
          >
            Season {seasonLabel}
            {typeof teamCount === "number" ? ` · ${teamCount} teams` : ""}
            {status ? ` · ${status}` : ""}
          </p>
        </div>
        <span
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "12px",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            border: "3px solid var(--ink)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 12px",
            background: isPartial ? "var(--yellow-light)" : "var(--green-light)",
            color: isPartial ? "var(--semantic-yellow)" : "var(--semantic-green)",
            transform: "rotate(-2deg)",
          }}
        >
          Coverage {coverage.status.toUpperCase()}
        </span>
      </div>

      {isPartial ? (
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "13px",
            lineHeight: 1.45,
            color: "var(--ink-medium)",
            margin: 0,
          }}
        >
          Scoring coverage is incomplete for the listed rules — those keys are not mapped
          into Razzle yet.
        </p>
      ) : null}

      <dl
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
          gap: "12px 16px",
          margin: 0,
        }}
      >
        <Fact label="Format" value={format} />
        <Fact label="Superflex" value={rules.superflex ? "yes" : "no"} />
        <Fact label="TE premium" value={tePremiumLabel(rules)} />
        <Fact label="Matchup" value={matchupLabel(rules.matchup.style)} />
        <Fact
          label="Playoffs"
          value={`${playoffTeams} teams · start week ${playoffStart}`}
        />
      </dl>

      {isPartial && coverage.unsupported_keys.length > 0 ? (
        <div
          style={{
            border: "3px solid var(--ink)",
            borderRadius: "var(--radius-sm)",
            background: "var(--yellow-light)",
            padding: "12px 14px",
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "13px",
              textTransform: "uppercase",
              margin: "0 0 8px",
              color: "var(--semantic-yellow)",
            }}
          >
            Unsupported keys
          </p>
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              display: "flex",
              flexDirection: "column",
              gap: "6px",
            }}
          >
            {coverage.unsupported_keys.map((item) => (
              <li
                key={`${item.key}-${String(item.value)}-${item.reason}`}
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "12px",
                  color: "var(--ink)",
                }}
              >
                <strong>{item.key}</strong>
                {` = ${String(item.value)}`}
                <span style={{ color: "var(--ink-medium)" }}>{` — ${item.reason}`}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          fontFamily: "var(--font-mono)",
          fontSize: "12px",
          color: "var(--ink-medium)",
        }}
      >
        <p style={{ margin: 0 }}>
          Revision{" "}
          <code style={{ color: "var(--ink)", wordBreak: "break-all" }}>
            {revision.revision_id}
          </code>
        </p>
        {revision.meta.sources.map((source) => (
          <p key={`${source.name}-${source.as_of}`} style={{ margin: 0 }}>
            {source.name}
            {" · as-of "}
            {formatAsOf(source.as_of)}
          </p>
        ))}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          alignItems: "center",
        }}
      >
        <Link
          href={scratchpadHref}
          className="btn-chunky"
          data-active="true"
          style={{ textDecoration: "none", display: "inline-block" }}
        >
          Open Scratchpad · carry revision in URL
        </Link>
        <button
          type="button"
          className="btn-chunky"
          onClick={onPullFresh}
          disabled={pullDisabled}
          title="Creates a new immutable revision from a fresh Sleeper pull"
          style={disabledControlStyle(pullDisabled)}
        >
          {pullPending ? "checking the tape..." : "Pull fresh revision"}
        </button>
      </div>
      <p
        style={{
          fontFamily: "var(--font-hand)",
          fontSize: "18px",
          color: "var(--ink-light)",
          margin: 0,
        }}
      >
        Pull fresh creates a new revision — reopening this URL only GETs the saved one.
        Scratchpad support for the carried revision is next.
      </p>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "11px",
          textTransform: "uppercase",
          color: "var(--ink-light)",
          margin: 0,
        }}
      >
        {label}
      </dt>
      <dd
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "14px",
          color: "var(--ink)",
          margin: "4px 0 0",
        }}
      >
        {value}
      </dd>
    </div>
  );
}
