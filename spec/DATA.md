# Data Contracts

## Identity — the crosswalk (T0 substrate)

- **Primary player key: nflverse `gsis_id`.** Every NFL stat table keys on it.
- **The crosswalk is one table (`player_ids`)**, seeded from the canonical `players` spine (every spine gsis_id gets a row; unmapped external ids stay NULL), overlaid by DynastyProcess `db_playerids.csv`, and enriched by the Sleeper players dump — exact keys only: gsis_id ⇄ sleeper_id ⇄ espn_id ⇄ pfr_id ⇄ cfb_player_id ⇄ market-source naming. Any adapter arriving keyed on anything other than gsis_id resolves **through the crosswalk table — never by name matching inside adapter code**. Unresolvable rows are logged in the sync report and skipped; guessing an identity is worse than dropping a row.
- **The college→pro bridge is keyed, not fuzzy** (verified 2026-07-22): nflverse `draft_picks.csv` carries `gsis_id`, `pfr_player_id`, and `cfb_player_id` side by side, plus college and draft capital. Drafted players link deterministically. Undrafted players go through name + college + class-year matching that **fails closed**: an unverified link renders "no verified college record," never a wrong attach. Bridge coverage is an audited number (target: ≥95% of drafted actives since 2016 linked, every link replayable).
- All stat values stored as **floats**.

## The accuracy law (T0 — gate G6)

The standard is **zero silent errors** — not "zero errors" as a slogan. Enforced, not aspired to:

1. **Traceability.** Every displayed number is reproducible along one path: source file → adapter map → DB row → API → surface. If a number can't be replayed, it doesn't ship.
2. **No invented precision.** Forecasts carry model + version + as-of. Calculated values state the rules they were computed under.
3. **Fail closed, visibly.** A league rule the engine can't compile (the coverage report, below) marks the league *partial*; affected surfaces show an "unsupported rule" chip. Nothing is silently guessed or silently scored wrong.
4. **Verification harness.** `scripts/verify_data.py` re-fetches N random rows per source and compares field-by-field against the DB (gate G6). Identity mismatches allowed: **zero**.
5. **Cross-source reconciliation.** Where two sources state the same fact (weekly receptions vs NGS; roster team vs depth chart), the harness compares them. A mismatch is flagged, never silently overwritten; the canonical source (this file's table) wins on the surface; persistent disagreement is a BLOCKED card.
6. **No silent coercion on identity.** `""`/`"NA"` → 0.0 is legal for counting stats only. Identity fields never coerce — bad identity means skip + log.
7. **Freshness stamps.** Every sync writes a `source_syncs` row (source, season, rows, fetched_at). Surfaces may show data-as-of; the harness flags stale sources. Team/roster truth comes from weekly records; static player metadata is assumed stale until stamped.

## The context kernel — `LeagueContextRevision`

**Every room reads the same revision; no room fetches Sleeper directly.**

- **Connect flow (live only):** Sleeper username → **that user's leagues, only theirs** → pick league → a revision is compiled and persisted. No demo-league surface exists in the product; recorded Sleeper JSON lives exclusively in the test suite as cassettes (CI never calls live Sleeper).
- A revision snapshots: compiled rules, rosters, matchups, standings, transactions, picks — each stamped source + as-of. Refresh creates a **new** revision; revisions are immutable.
- **The rules compiler:** `compile_league(sleeper_json) → CompiledRules` — maps Sleeper `scoring_settings` onto the scoring engine (already a superset: two-point conversions, sacks, TE premium, first downs), detects format (dynasty/redraft, superflex, **H2H vs H2H+median**, playoff weeks, tiebreakers), and emits a **coverage report** (supported / unsupported keys). Golden tests pin known leagues.
- **Scenarios are immutable overlays** (`trade`, `injury_out`, `lineup_change`, `waiver`) referencing a base revision. Engines accept `context = revision | scenario`. A scenario never mutates real league data.
- **The provenance envelope:** every meaningful API response carries `meta: {revision, sources: [{name, as_of, version}], coverage, assumptions, model_version?}` — the mechanical form of the data classes in `spec/NORTH_STAR.md` (Recorded / Calculated / Forecast / Scenario / Recommendation).

## One database, Alembic-owned

`data/razzle.db` (SQLite, gitignored). The Alembic migration chain in `apps/api/migrations/` is the machine truth for the schema. Every schema change is a migration — no ad-hoc DDL. **Migrations are authored only by the captain seat** (`factory/ROUTING.md`) — the chain is serial by nature and is never a fleet surface.

Canonical tables (grow via migrations as slices demand): `players` · `player_ids` · `player_meta` · `player_week_stats` (columns mirror `razzle_api.domain.scoring.engine.PlayerWeekStats`) · per-source weekly tables (snaps, injuries, depth charts, NGS, PFR advanced, FTN, QBR) · `games` (schedule, results, vegas) · `contracts`, `draft_picks`, `combine` · `market_values` (source, format, value, fetched_at) · `college_season_stats` · `leagues`, `context_revisions`, `scenarios` · `source_syncs`.

**Size budget: dev database < 200 MB with full history** (NFL weekly 1999–2025 ≈ 170k rows lands ~30–40 MB; the budget leaves headroom for the per-source weekly tables). **Play-by-play is explicitly excluded** (900 MB class) until a slice proves the need. `--quick` sync mode (current + prior season) stays for fast dev loops; `--full` backfills history.

## Adapter pattern (fleet-safe)

One adapter per source: **fetch → clean → resolve identity via crosswalk → normalize → upsert canonical tables.** Each adapter is one self-contained module `apps/api/src/razzle_api/ingest/<source>.py` exposing `sync(session, seasons) -> SyncReport`. `scripts/sync_data.py` discovers adapters through a name → module-path registry with lazy imports, so **adding a source never edits another adapter**. Syncs are **idempotent**. Ingest is app code, not domain; the domain layer never does I/O.

## Sources — the verified keyless stack

All URLs verified live 2026-07-22 (HTTP 200, no credentials). GitHub API calls need a `User-Agent` header; `players.csv` is BOM-encoded (`utf-8-sig`). **Historical depth is in scope: NFL weekly 1999–2025; college 2014–2025 (earlier college files do not exist — verified).**

### Core (shipped — S-001)

| # | Source | What | Where |
|---|--------|------|-------|
| 1 | **nflverse players** | Identity spine: gsis_id, name, position | `…/releases/download/players/players.csv` |
| 2 | **nflverse weekly stats** | One row per player-week, scoring-engine shaped, **1999–2025** | release `stats_player`, `stats_player_week_{season}.csv` |

### Usage & context (the "why" behind every stat line)

| # | Source | What | Where |
|---|--------|------|-------|
| 3 | **nflverse snap counts** | Offense/defense/ST snaps + snap % per week | release `snap_counts`, `snap_counts_{season}.csv` |
| 4 | **nflverse injuries** | Weekly practice/report status, designations | release `injuries`, `injuries_{season}.csv` |
| 5 | **nflverse depth charts** | Weekly depth-chart slot per team | release `depth_charts`, `depth_charts_{season}.csv` |
| 6 | **nflverse weekly rosters** | Age, height, weight, years_exp, headshot, status — weekly truth beats static metadata | release `weekly_rosters`, `roster_weekly_{season}.csv` |
| 7 | **nfldata games** | Schedule, results, rest days, **vegas spread/total** | `raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv` |

### Advanced (the film-room layer nobody else surfaces together)

| # | Source | What | Where |
|---|--------|------|-------|
| 8 | **Next Gen Stats** | Separation, aDOT, time-to-throw, xYAC, RYOE | release `nextgen_stats`, **combined** `ngs_{passing\|receiving\|rushing}.csv.gz` filtered to synced seasons (per-season files stop at 2024 — verified) |
| 9 | **PFR advanced** | Pressures, hurries, broken tackles, drops, air yards | release `pfr_advstats`, `advstats_week_{pass\|rush\|rec\|def}_{season}.csv` |
| 10 | **FTN charting** | Routes vs man/zone, play action, screens, motion (2022+) | release `ftn_charting`, `ftn_charting_{season}.csv` |
| 11 | **ESPN QBR** | Weekly QBR | release `espn_data`, `qbr_week_level.csv` |

### Career, pedigree & the college bridge (dynasty fuel)

| # | Source | What | Where |
|---|--------|------|-------|
| 12 | **OTC contracts** | Value, APY, guarantees, years — the "expiring contract" thesis | release `contracts`, `historical_contracts.csv.gz` (**only the .gz exists** — verified) |
| 13 | **Draft picks** | Round, pick, college, **gsis_id ⇄ cfb_player_id bridge** | release `draft_picks`, `draft_picks.csv` |
| 14 | **Combine** | 40, bench, vert, cone | release `combine`, `combine.csv` |
| 15 | **cfbfastR college** | College player season stats, **2014–2025** | `raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/player_stats/csv/player_stats_{season}.csv` |

### Market & league (the intrinsic-vs-market gap that IS the trade thesis)

| # | Source | What | Where |
|---|--------|------|-------|
| 16 | **FantasyCalc API** | Live market values by format (public API) | `api.fantasycalc.com/values/current?isDynasty={bool}&numQbs={1\|2}&numTeams={n}&ppr={0\|0.5\|1}` |
| 17 | **DynastyProcess values** | Market values (1QB + SF), weekly, MIT-licensed + `db_playerids.csv` crosswalk | `raw.githubusercontent.com/dynastyprocess/data/master/files/values-players.csv` |
| 18 | **Sleeper API** | Players dump (~14 MB JSON — cache 24h in `data/cache/`), trending, user → leagues → rosters → matchups → transactions → drafts, scoring settings | `api.sleeper.app/v1/…` |

**Market-source law: permissioned or licensed only.** FantasyCalc (public API) and DynastyProcess (MIT) are in; **scraping proprietary sites (KTC and friends) is forbidden.** Licensed projection/value feeds are a post-Milestone-Zero integration; until then, forecasts are our own labeled models.

Reference implementations (read-only, do not import): `graveyard/razzle/legacy/adapters/`.

## Flow in one line

**nflverse (13 releases, 1999–) + nfldata + college (2014–) + market sources + Sleeper → crosswalk → razzle.db → compiled rules → revisions & scenarios → pure engines (scoring / standings / valuation / simulation) → Scratchpad, The Line, War Room, Player Sheet.**

Values (fantasy points, VORP) are computed from stats + `CompiledRules` at request time — not stored — until profiling proves a cache is needed.
