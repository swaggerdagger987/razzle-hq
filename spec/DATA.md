# Data Contracts

## Identity — the crosswalk (T0 substrate)

- **Primary player key: nflverse `gsis_id`.** Every stat table keys on it.
- **The crosswalk is one table (`player_ids`)**, built from DynastyProcess `db_playerids.csv` enriched by the Sleeper players dump: gsis_id ⇄ sleeper_id ⇄ espn_id ⇄ pfr_id ⇄ mfl_id ⇄ fantasycalc/ktc naming. Any adapter arriving keyed on anything other than gsis_id resolves **through the crosswalk table — never by name matching inside adapter code**. Unresolvable rows are logged in the sync report and skipped; guessing an identity is worse than dropping a row.
- All stat values stored as **floats**.

## The accuracy law (T0 — gate G6)

Zero tolerance for player-accuracy mistakes. Enforced, not aspired to:

1. **Traceability.** Every displayed number is reproducible along one path: source file → adapter map → DB row → API → surface. If a number can't be replayed, it doesn't ship.
2. **Verification harness.** `scripts/verify_data.py` re-fetches N random rows per source and compares field-by-field against the DB (gate G6 in `factory/GATES.md`). Identity mismatches allowed: **zero**.
3. **Cross-source reconciliation.** Where two sources state the same fact (weekly receptions vs NGS receptions; roster team vs depth-chart team), the harness compares them. Disagreements land in the sync report; the canonical source (this file's table) wins on the surface; a persistent disagreement is a BLOCKED card, not a judgment call.
4. **No silent coercion on identity.** `""`/`"NA"`/`"NaN"` → 0.0 is legal for counting stats only. Identity fields (ids, names, teams, positions) never coerce — bad identity means skip + log.
5. **Freshness stamps.** Every sync writes a `source_syncs` row (source, season, rows, fetched_at). Surfaces may show data-as-of; the harness flags stale sources.

## One database, Alembic-owned

`data/razzle.db` (SQLite, gitignored). The Alembic migration chain in `apps/api/migrations/` is the machine truth for the schema; this doc explains intent. Every schema change is a migration — no ad-hoc DDL in app code. In swarm runs, **migrations are authored only by the architect seat in Wave 0** (`factory/ROUTING.md`) — the chain is serial by nature and is never a fleet surface.

Canonical tables (grow via migrations as slices demand): `players` (identity) · `player_ids` (crosswalk) · `player_meta` (age, height, weight, years_exp, headshot, status, college) · `player_week_stats` (columns mirror `razzle_api.domain.scoring.engine.PlayerWeekStats` so rows load straight into the engine) · per-source weekly tables (snaps, injuries, depth charts, NGS, PFR advanced, FTN, QBR) · `games` (schedule, scores, vegas) · `contracts`, `draft_picks`, `combine` · `market_values` (source, format, value, fetched_at) · `college_season_stats` · `leagues` (Sleeper league + `LeagueConfig` JSON) · `source_syncs`.

**Size budget: dev database < 100 MB.** `--quick` mode (current + prior season) stays lean. **Play-by-play is explicitly excluded** (900 MB class) until a slice proves the need; everything below fits the budget.

## Adapter pattern (swarm-safe)

One adapter per source: **fetch → clean → resolve identity via crosswalk → normalize → upsert canonical tables.** Each adapter is one self-contained module `apps/api/src/razzle_api/ingest/<source>.py` exposing `sync(session, seasons) -> SyncReport`. `scripts/sync_data.py` discovers adapters through a name → module-path registry with lazy imports, so **adding a source never edits another adapter** — a fleet agent's fence is its own module plus one registry line. Syncs are **idempotent** — re-running upserts, never duplicates. Ingest is app code, not domain; the domain layer never does I/O.

## Sources — the verified keyless stack

All URLs verified live 2026-07-22 (HTTP 200, no credentials). GitHub API calls need a `User-Agent` header; `players.csv` is BOM-encoded (`utf-8-sig`).

### Core (shipped — S-001)

| # | Source | What | Where |
|---|--------|------|-------|
| 1 | **nflverse players** | Identity spine: gsis_id, name, position | `…/releases/download/players/players.csv` |
| 2 | **nflverse weekly stats** | One row per player-week, scoring-engine shaped | release `stats_player`, `stats_player_week_{season}.csv` |

### Usage & context (the "why" behind every stat line)

| # | Source | What | Where |
|---|--------|------|-------|
| 3 | **nflverse snap counts** | Offense/defense/ST snaps + snap % per week | release `snap_counts`, `snap_counts_{season}.csv` |
| 4 | **nflverse injuries** | Weekly practice/report status, injury designations | release `injuries`, `injuries_{season}.csv` |
| 5 | **nflverse depth charts** | Weekly depth-chart slot per team | release `depth_charts`, `depth_charts_{season}.csv` |
| 6 | **nflverse weekly rosters** | Age, height, weight, years_exp, headshot_url, status | release `weekly_rosters`, `roster_weekly_{season}.csv` |
| 7 | **nfldata games** | Schedule, results, rest days, **vegas spread/total** | `raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv` |

### Advanced (the film-room layer nobody else surfaces together)

| # | Source | What | Where |
|---|--------|------|-------|
| 8 | **Next Gen Stats** | Separation, aDOT, time-to-throw, xYAC, rush yards over expected | release `nextgen_stats`, **combined** `ngs_{passing\|receiving\|rushing}.csv.gz` filtered to synced seasons (per-season files stop at 2024 — verified) |
| 9 | **PFR advanced** | Pressures, hurries, broken tackles, drops, air yards | release `pfr_advstats`, `advstats_week_{pass\|rush\|rec\|def}_{season}.csv` |
| 10 | **FTN charting** | Routes vs man/zone, play action, screens, motion (2022+) | release `ftn_charting`, `ftn_charting_{season}.csv` |
| 11 | **ESPN QBR** | Weekly QBR | release `espn_data`, `qbr_week_level.csv` |

### Career & pedigree (dynasty fuel)

| # | Source | What | Where |
|---|--------|------|-------|
| 12 | **OTC contracts** | Value, APY, guarantees, years — the "expiring contract" thesis | release `contracts`, `historical_contracts.csv.gz` (**only the .gz exists** — verified) |
| 13 | **Draft picks** | Round, pick, class year | release `draft_picks`, `draft_picks.csv` |
| 14 | **Combine** | 40, bench, vert, cone | release `combine`, `combine.csv` |
| 15 | **cfbfastR college** | College season stats, prospect bridge | `raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/player_stats/csv/player_stats_{season}.csv` |

### Market & league (the intrinsic-vs-market gap that IS the trade thesis)

| # | Source | What | Where |
|---|--------|------|-------|
| 16 | **FantasyCalc API** | Live market values by format | `api.fantasycalc.com/values/current?isDynasty={bool}&numQbs={1\|2}&numTeams={n}&ppr={0\|0.5\|1}` |
| 17 | **DynastyProcess values** | KTC-derived weekly values (1QB + SF) + `db_playerids.csv` crosswalk | `raw.githubusercontent.com/dynastyprocess/data/master/files/values-players.csv` |
| 18 | **Sleeper API** | Players dump (~14 MB JSON — cache 24h in `data/cache/`), trending adds/drops, user → leagues → rosters → matchups → transactions → drafts, league scoring settings → `LeagueConfig` | `api.sleeper.app/v1/…` |

Reference implementations (read-only, do not import): `graveyard/razzle/legacy/adapters/` — proven URL handling, column maps, edge cases.

## Flow in one line

**nflverse (13 releases) + nfldata + Sleeper + market sources → crosswalk → razzle.db → scoring/valuation domain (per-league rules) → rooms + staff context.** Market values land *beside* computed intrinsic values, never in place of them — the gap is the product.

Values (fantasy points, VORP) are computed from stats + `LeagueConfig` at request time — not stored — until profiling proves a cache is needed.
