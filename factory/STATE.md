# State

## NOW

- **Active slice:** none — S-005 is next (sketch)
- **Launch deadline:** **2026-07-28** (live + Reddit-shareable before draft season; scope bends, date doesn't)
- **Launch-critical path:** S-001 ✅ → S-002 ✅ → S-003 ✅ → S-004 ✅ → S-005 → S-006 → S-007 → S-008
- **Blockers:** none
- **Last commit:** S-004 explore-custom-scoring — Scoring presets (Standard/PPR/Half/TEP) + custom rules picker; fantasy-points column computed server-side; URL state via nuqs; Player Sheet inherits scoring
- **Date:** 2026-06-13

## BACKLOG

### S-001 nflverse-ingest [DONE]
- **Pillar/Layer:** Data (Explore L0 prerequisite) · **Trust:** T1 substrate
- **Goal:** `uv run python scripts/sync_data.py --quick` fills `players` + `player_week_stats` from nflverse for seasons 2024–2025; `GET /api/players` serves it.
- **File plan:**
  - NEW `apps/api/src/razzle_api/ingest/__init__.py` — docstring only.
  - NEW `apps/api/src/razzle_api/ingest/nflverse.py` — the adapter (fetch + map + upsert).
  - NEW `apps/api/src/razzle_api/services/players_service.py` — `list_players(session, position, limit)`.
  - NEW `apps/api/src/razzle_api/api/routers/players.py` + `api/schemas/players.py`.
  - EDIT `apps/api/src/razzle_api/main.py` — one import + one `include_router` line.
  - NEW `scripts/sync_data.py` — argparse CLI: `--quick` (seasons 2024+2025), `--seasons 2023 2024`, `--status` (print row counts + db file size, no fetch).
  - NEW `apps/api/tests/unit/test_nflverse_mapping.py`, `apps/api/tests/integration/test_players_api.py`.
- **Interfaces:**
  - `fetch_players() -> list[dict]` and `fetch_week_stats(season: int) -> list[dict]` — network only, no DB. Stdlib urllib + csv (+ gzip for `.gz`), `User-Agent: razzle-sync/1.0`, timeout 120s.
  - `map_week_row(row: dict) -> dict | None` — pure: one nflverse CSV row → our column dict, or None if filtered out. This is the unit-tested function.
  - `upsert_players(session, rows) -> int`, `upsert_week_stats(session, season, rows) -> int` — DB only, no network. SQLite upsert via `sqlalchemy.dialects.sqlite.insert(...).on_conflict_do_update(...)`; conflict targets: `gsis_id` / `(player_id, season, week)`.
  - `GET /api/players?position=RB&limit=100` → `{"players": [{"gsis_id", "name", "position", "team"}]}`, ordered by name; `limit` default 100, max 500.
- **Data contract:**
  - Players: `https://github.com/nflverse/nflverse-data/releases/download/players/players.csv` — take `gsis_id` (PK; skip rows without one), `display_name`→name, `position`, `latest_team`→team. Keep positions QB/RB/WR/TE only.
  - Weekly: release tag `stats_player`, file `stats_player_week_{season}.csv`, found via `https://api.github.com/repos/nflverse/nflverse-data/releases?per_page=100` (or direct download URL of the same shape as players). Keep rows where `season_type == "REG"` and position in QB/RB/WR/TE. **The weekly file's `player_id` column IS the gsis_id.**
  - Column map (nflverse → ours): `attempts`→pass_att · `completions`→pass_cmp · `passing_yards`→pass_yd · `passing_tds`→pass_td · `passing_interceptions` (older files: `interceptions`)→pass_int · `sacks_suffered` (older: `sacks`)→pass_sack · `passing_2pt_conversions`→pass_two_pt · `carries`→rush_att · `rushing_yards`→rush_yd · `rushing_tds`→rush_td · `rushing_2pt_conversions`→rush_two_pt · `targets`→target · `receptions`→rec · `receiving_yards`→rec_yd · `receiving_tds`→rec_td · `receiving_2pt_conversions`→rec_two_pt · fumble = `rushing_fumbles`+`receiving_fumbles`+`sack_fumbles` · fumble_lost = same three `_lost` columns · `special_teams_tds`→special_teams_td. All other schema columns stay 0.
  - Coercion: `""`/`"NA"`/`"NaN"`/None → 0.0; everything to float. The map must accept BOTH old and new column names (the 2025+ format renamed exactly: passing_interceptions, sacks_suffered, sack_yards_lost, team→recent_team).
- **Test plan:** unit — `map_week_row` on two literal fixture dicts (one new-format, one old-format names) asserts identical mapped output, NA→0.0, non-REG row → None. Integration — on a tmp migrated DB: upsert fixture players+stats twice, assert row counts identical both times (idempotency) and a known value survives; seed 3 players, `GET /api/players?position=RB` via ASGITransport returns the RBs only.
- **Gates:** G1–G4; G5 (paste outputs in commit body):
  - `uv run python scripts/sync_data.py --quick` → exit 0
  - `uv run python scripts/sync_data.py --status` → players ≥ 500, week-stat rows ≥ 10000, db size < 100MB
  - run `--quick` again, then `--status` → identical row counts
  - `curl -s 'localhost:8000/api/players?position=RB&limit=50' | python3 -c "import json,sys; print(len(json.load(sys.stdin)['players']))"` → ≥ 20
- **Out of scope:** kicking columns (stay 0), DST/IDP, return_yd/return_td (stay 0), college data, snap counts, injuries, schedules, storing nflverse's precomputed fantasy_points columns (we always compute from rules), any UI.
- **Pitfalls (verified against the legacy adapter, read-only ref: old razzle repo `legacy/adapters/nflverse_adapter.py`):** GitHub releases API requires a User-Agent header · players.csv uses BOM, decode `utf-8-sig` · don't trust `players.csv` team for identity (teams go stale), gsis_id only · keep `ingest/` importing the engine's column names from one place: define `STAT_COLUMNS` once (the migration already has the list — mirror it, don't import the migration).

### S-002 explore-screener [DONE]
- **Pillar/Layer:** Explore L0–L1 · **Trust:** T1, T6
- **Goal:** `/explore` — season-total screener over real synced data: position filter, sortable columns, nuqs URL state, position colors, "pulling film..." loading state.
- **File plan:**
  - NEW `apps/api/src/razzle_api/services/screener_service.py` — `list_season_totals(...)` (the aggregation query).
  - NEW `apps/api/src/razzle_api/api/routers/screener.py` + `api/schemas/screener.py`.
  - EDIT `apps/api/src/razzle_api/main.py` — one import + one `include_router` line.
  - NEW `apps/api/tests/integration/test_screener_api.py`.
  - EDIT `apps/web/package.json` — add deps `@tanstack/react-query@^5`, `@tanstack/react-table@^8`, `nuqs@^2`; run `pnpm install` and COMMIT `pnpm-lock.yaml` (CI uses `--frozen-lockfile`).
  - NEW `apps/web/src/app/providers.tsx` — client component: `QueryClientProvider` + `NuqsAdapter` (from `nuqs/adapters/next/app`).
  - EDIT `apps/web/src/app/layout.tsx` — wrap `{children}` in `<Providers>`.
  - NEW `apps/web/src/app/explore/page.tsx` — route shell, renders the feature.
  - NEW `apps/web/src/features/explore/api.ts` — typed `fetchScreener` (same `API_URL` pattern as `scoring-preview/api.ts`).
  - NEW `apps/web/src/features/explore/ScreenerPanel.tsx` — client component: nuqs state, TanStack Query fetch, position filter pills, table.
  - NEW `apps/web/src/features/explore/ScreenerTable.tsx` — TanStack Table v8: sortable headers, position-color badges, zebra rows.
- **Interfaces:**
  - `GET /api/screener?season=2025&position=RB&sort=rush_yd&dir=desc&limit=100&offset=0` → `{"season": 2025, "total": <int>, "rows": [ScreenerRow]}`. `ScreenerRow` = `{gsis_id, name, position, team, games, pass_att, pass_cmp, pass_yd, pass_td, pass_int, rush_att, rush_yd, rush_td, target, rec, rec_yd, rec_td, fumble_lost}` — identity strings, everything else float (games int).
  - Param rules: `season` int default 2025 · `position` optional, must be QB/RB/WR/TE (else 422) · `sort` must be `name`, `games`, or one of the 13 stat keys above, default `name` (else 422) · `dir` `asc`/`desc`, default `asc` for name, `desc` otherwise · `limit` 1–500 default 100 · `offset` ≥ 0 default 0. Validate with FastAPI `Query`/`Literal`; the service trusts its inputs.
  - `list_season_totals(session, *, season, position, sort, descending, limit, offset) -> tuple[list[dict], int]` — SQLAlchemy Core over `players_table`/`player_week_stats_table` (import from `ingest/nflverse.py`, same as `players_service`): JOIN on gsis_id, `WHERE season = :season` (+ position), `GROUP BY` player, `COUNT(week) AS games`, `SUM(col) AS col` for the 13 stats, ORDER BY sort col + `gsis_id` tiebreak, LIMIT/OFFSET; second return value = ungated player count for the same filters.
  - `total` requires a second COUNT query (or subquery) — same WHERE, no limit.
- **Web contract:**
  - URL is source of truth: nuqs `useQueryStates` for `season` (int, default 2025), `position` (string or null), `sort` (default `name`), `dir`. Changing any control updates the URL; loading `/explore?position=RB&sort=rush_yd&dir=desc` cold reproduces the exact view.
  - TanStack Query key `["screener", season, position, sort, dir]`; manual server-side sorting (table `manualSorting: true`, header click writes nuqs state, NOT client sort).
  - Design (`spec/DESIGN.md`, tokens only): page on `--bg`, table card `--bg-card` with 3px solid `var(--ink)` border + `var(--shadow-chunky)`; header row `--bg-warm`; data cells `--font-mono` 13px; player names `--font-display`; position badge per row tinted `var(--pos-qb|rb|wr|te)`; zebra `var(--zebra-stripe)`; sorted column header highlighted with `--orange`. Loading state: "pulling film..." in `--font-hand` 24px. Explicit error ("film room's dark. try again.") and empty ("no players match that cut.") states.
  - Hallway: header links back to `/` and to `/scoring` (`crossRoomLinkPresent`); player-row → Player Sheet link is S-003's first move (rows are plain text here — logged, not a dead-end violation since the route doesn't exist yet).
- **Test plan (`test_screener_api.py`, reuse the `session_factory` + dependency-override pattern from `test_players_api.py`):** seed 2 RBs + 1 QB with 2 weeks each of 2024 stats → `season totals are summed and games counted` (known player: rush_yd = wk1+wk2, games = 2) · `sort=rush_yd&dir=desc orders correctly` · `position=RB returns only RBs` and `total` matches · `sort=evil_column returns 422` · `position=K returns 422` · `season with no rows returns empty rows, total 0, not 500`.
- **Gates:** G1–G4; G5 (paste outputs in commit body):
  - `curl -s 'localhost:8000/api/screener?season=2025&position=RB&sort=rush_yd&dir=desc&limit=50' | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['rows']), d['rows'][0]['name'])"` → `50 <a real RB1>` against the synced db
  - rush_yd of row[0] ≥ row[1] ≥ row[2] (paste first three)
  - `/explore` renders ≥20 rows; clicking a header or position pill updates the URL; hard refresh on that URL preserves the exact view; no 500s in API log
  - voice check: `grep -rEn '\bAI\b|powered by|chatbot|LLM' apps/web/src --include='*.tsx'` → no user-facing hits
  - screenshot of `/explore?position=RB&sort=rush_yd&dir=desc` attached to the session (sand bg, chunky border, RB teal badges) — would r/DynastyFF screenshot it?
- **Out of scope:** fantasy-points column and scoring presets (S-004) · player-row links to Player Sheet (S-003) · virtualization, 100+ columns, college toggle (Explore L1+) · saved views, export, watermark · pagination UI beyond limit/offset params · any new table or migration.
- **Pitfalls:** nuqs v2 throws without `NuqsAdapter` mounted above any `useQueryState` call · keep `page.tsx` a server component and the panel `"use client"` (nuqs + TanStack hooks are client-only) · TanStack Table v8 column defs must be memoized (`useMemo`) or the table re-mounts every render · SQLite `SUM` returns NULL for no rows — wrap aggregates in `COALESCE(..., 0)` or coerce in the service · sort param goes through a whitelist dict to a column object, never string-interpolated into SQL · CI runs `pnpm install --frozen-lockfile`: forgetting to commit the updated `pnpm-lock.yaml` fails the web job.

### S-003 player-sheet-v0 [DONE]
- **Pillar/Layer:** Player Sheet · **Trust:** T3
- **Goal:** `/player/[gsis_id]` — header (name/team/position color), season + weekly stat table, prev/next player switch; every Explore row links here.
- **File plan:**
  - NEW `apps/api/src/razzle_api/api/routers/players_detail.py` — `GET /api/players/{gsis_id}` endpoint.
  - NEW `apps/api/src/razzle_api/api/schemas/players_detail.py` — `PlayerDetail` response (gsis_id, name, position, team, seasons: [{ season, week_stats }]).
  - NEW `apps/web/src/app/player/[gsis_id]/page.tsx` — server component, wraps `<PlayerSheet gsis_id={params.gsis_id} />`.
  - NEW `apps/web/src/features/player-sheet/PlayerSheet.tsx` — client component, renders header + season picker + stat table + prev/next nav.
  - NEW `apps/web/src/features/player-sheet/PlayerHeader.tsx` — name, position badge (colored), team.
  - NEW `apps/web/src/features/player-sheet/StatTable.tsx` — season + week columns, all 13 stats, sortable.
  - NEW `apps/web/src/features/player-sheet/PrevNextNav.tsx` — prev/next player buttons (navigates to adjacent gsis_id in sorted list context, or just disable if context not available).
  - NEW `apps/api/tests/integration/test_players_detail_api.py` — seed player, verify GET returns full stats.
- **Interfaces:**
  - `GET /api/players/{gsis_id}` → `{ gsis_id, name, position, team, seasons: [{ season: int, week_stats: [{ week, col1, col2, ... }] }] }`.
  - Service function: `get_player_detail(session, gsis_id) -> dict` — joins players + player_week_stats, groups by season.
- **Web contract:**
  - URL: `/player/[gsis_id]` — navigate from Explore row click (Explore's ScreenerTable rows become links to `/player/{row.gsis_id}`).
  - Season picker: dropdown or tabs, default to 2025; clicking a season re-renders the stat table.
  - Stat table: 13 stat columns + week column, clickable row to view/compare (not required here, just clickable).
  - Prev/next: buttons to go to previous/next player in the season (e.g., next by gsis_id alphabetically, or prev/next in the sync order).
  - Design: position badge (colored, e.g., RB=teal) in header; clean stat table, `--font-mono` for numbers, position-colored row hover (light tint).
  - Hallway: header link back to `/explore`; Player Sheet is the hub (future: Bureau context, Room ask, Trade ideation all reach from here).
- **Test plan:**
  - seed Saquon Barkley + Jonathan Taylor with 2 seasons each, 2 weeks of stats per season.
  - `GET /api/players/{saquon_gsis_id}` → seasons list has 2 items, first season has ≥2 week rows.
  - Web: landing on `/player/{saquon_gsis_id}` renders name + position, season picker defaults to 2025, stat table has rows.
  - Prev/next: buttons exist and are clickable (functional nav tested separately).
- **Out of scope:** trade valuation (S-005) · staff commentary · league context · stat filters/export · comparing two players side-by-side (future).
- **Pitfalls:** nuqs not needed here (season picker is component-local state, not URL); player_week_stats may have weeks out of order if sync was interrupted, but that's a data integrity issue not this slice's concern · don't over-style the table — stat data speaks for itself.
- **T6 note:** position color in the header (warm not generic), clean table design that makes the numbers the focus. Loading: "pulling up the tape..." when fetching. Empty/error states: "player not found" if gsis_id invalid.
- **Gates:** G1–G4; G5 (paste outputs in commit body):
  - `curl -s 'localhost:8000/api/players/{saquon_gsis_id}' | jq '.seasons[0].week_stats | length'` → ≥ 2
  - `/player/{saquon_gsis_id}` renders name "Saquon Barkley", position badge tinted correctly, season picker loads, stat table has ≥2 rows
  - clicking prev/next is non-error (no 500s in API log)
  - hard refresh on `/player/{saquon_gsis_id}` preserves the view (no loading jank)
  - screenshot of the page: would r/DynastyFF screenshot this? (clean, focused on data, warm design colors)

### S-004 explore-custom-scoring [DONE]
- **Pillar/Layer:** Explore L3 · **Trust:** T1, T3
- **Goal:** Scoring preset picker (PPR/half/standard/TEP from `domain/scoring/presets.py`) + editable core rules; fantasy-points column computed server-side by `score_week` over real week stats.
- **File plan:**
  - EDIT `apps/api/src/razzle_api/api/routers/screener.py` — add `scoring_preset` and `scoring_rules` (JSON string) query params.
  - EDIT `apps/api/src/razzle_api/services/screener_service.py` — `list_season_totals` now accepts `scoring_config: ScoringConfig` and calls `score_week` on each row, appends `fantasy_points` to output.
  - EDIT `apps/api/src/razzle_api/api/schemas/screener.py` — `ScreenerRow` adds `fantasy_points: float` field.
  - EDIT `apps/web/src/features/explore/ScreenerPanel.tsx` — add preset picker (tabs: Standard/PPR/Half/TEP), rules editor (simplified: toggle-able scoring multipliers), nuqs state for `scoring_preset` + `scoring_rules`.
  - EDIT `apps/web/src/features/explore/ScreenerTable.tsx` — add fantasy-points column, sortable.
  - EDIT `apps/web/src/features/explore/api.ts` — `fetchScreener` now passes `scoring_preset` and `scoring_rules` to the API.
  - EDIT `apps/web/src/features/player-sheet/PlayerSheet.tsx` — Player Sheet inherits `scoring_preset` from URL query param (T3 hallway integration).
  - NEW `apps/api/tests/integration/test_screener_scoring_api.py` — seed stats, verify fantasy_points computed correctly per preset; verify preset change updates points.
- **Interfaces:**
  - `GET /api/screener?season=2025&position=RB&sort=rush_yd&dir=desc&scoring_preset=PPR&scoring_rules={"pass_td":6}` → same ScreenerResponse, `ScreenerRow` now has `fantasy_points` field.
  - Query params: `scoring_preset` (Literal["standard", "PPR", "half", "TEP"], default "standard") · `scoring_rules` (optional JSON string, if set overrides the preset).
  - Service: `list_season_totals(..., scoring_config: ScoringConfig = None)` — if None, use default (standard); otherwise use preset or rules. For each row, compute `fantasy_points = sum(score_week(stat_col, scoring_config) for stat_col in stats)`.
- **Data contract:**
  - Presets: import `ScoringConfig` and presets from `apps/api/src/razzle_api/domain/scoring/presets.py` (already exists, no changes needed).
  - `score_week` function (from domain/scoring/engine.py): takes a player's week stats dict + ScoringConfig, returns total fantasy points for that week.
  - Season totals fantasy_points = sum of all weeks' fantasy_points for that season.
- **Web contract:**
  - URL state: nuqs `scoring_preset` (string, default "standard") + `scoring_rules` (string or null). Changing preset updates URL; hard refresh reproduces exact view.
  - Preset tabs: visually distinct, active tab tinted `--orange`.
  - Rules editor: simplified — show 3–4 key rules (pass_td, rush_td, rec_td, rec_yd_per_pt) with +/- buttons to adjust multipliers (e.g., 6pt vs 4pt TD). Don't expose all 30 columns.
  - Fantasy-points column: right-aligned, `--font-mono`, sorted descending by default. No highlight, just data.
  - Design: same as S-002 (sand bg, chunky border, position colors).
- **Test plan:**
  - Seed 1 RB with 1 week of stats (e.g., 100 rush_yd, 1 rush_td, 0 targets).
  - Standard scoring: fantasy_points = 100/10 + 6 = 16.
  - PPR preset: fantasy_points = 100/10 + 6 + (if 0 targets, no PPR bonus) = 16.
  - Custom rules (pass_td=4): verify points recomputed if a QB has pass_tds.
  - API returns `fantasy_points` field, matches domain/scoring/engine unit test values.
  - Web: preset picker changes URL; hard refresh shows same points; changing a rule updates the column live (TanStack Query refetch).
- **Out of scope:** save custom rules as templates (future, League L2) · "best ball" scoring · DFS scoring · stat projections · backfill scoring on historical weeks.
- **Pitfalls:** `score_week` is unit-tested in `test_scoring_engine.py`; don't re-implement, just call it · `scoring_rules` as a JSON string is fragile for large edits, but OK for this MVP (L3, not L4+) · SQLAlchemy doesn't compute, so season totals fantasy_points must be sum-of-weeks in Python, not a SQL aggregate (cost is bearable for 50 rows).
- **T6 note:** loading: "calculating your league's points...", preset tabs feel "live" (no page reload on click), fantasy-points column renders cleanly (no extra flair, let data speak).
- **Gates:** G1–G4; G5 (paste outputs in commit body):
  - `curl -s 'localhost:8000/api/screener?season=2025&position=RB&sort=fantasy_points&dir=desc&scoring_preset=PPR' | jq '.rows[0] | {name, fantasy_points}'` → `{ "name": "...", "fantasy_points": <float> }`
  - Verify first 3 fantasy_points values match a manual calc: seed 1 RB with 100 rush_yd + 1 rush_td, standard = 16 (100/10 + 6).
  - `/explore?scoring_preset=PPR` loads; clicking Standard tab updates URL to `?scoring_preset=standard`; hard refresh shows same view.
  - Editing a rule (e.g., pass_td from 6 to 4) visibly updates the fantasy_points column (TanStack Query refetch completes, column re-renders).
  - voice check: no AI/LLM hits.
  - screenshot: preset tabs visible, fantasy-points column visible, numbers are clean (not excessive decimals).

### S-005 valuation-workbench-v0 [OPEN]
- **Pillar/Layer:** Lab L1–L3 (flagship; absorbs Launch-10 `vorp`) · **Trust:** T1, T5, T6
- **Goal:** `/lab/workbench` — the income approach made visible. VORP over a real season is the first model: assumptions panel (scoring config, replacement logic, league size) on the left, tier-colored value table on the right, values recompute live as assumptions change. Methodology note rendered beside the numbers ("how this value is built"). Octo header.
- **Scope:** `apps/web/src/app/lab/`, `apps/web/src/features/lab/`, valuation service wiring to real data, tests.
- **Gates:** G1–G4; G5: real top-200 renders, position ranks correct vs `test_vorp.py` logic, changing an assumption visibly moves values, links back to Player Sheet (hallway `crossRoomLinkPresent`), screenshot passes the r/DynastyFF test.

### S-006 sleeper-connect [OPEN]
- **Pillar/Layer:** Bureau L0 · **Trust:** T2
- **Goal:** Sleeper username → league list → pick league; persist `LeagueConfig` (new `leagues` migration); context bar shows `@user · league`; workbench + screener default to the connected league's scoring.
- **Scope:** to be fenced by a frontier planning pass before activation.
- **Gates:** to be defined when fenced.

### S-007 trade-answer-card [OPEN]
- **Pillar/Layer:** Explore/Lab (distribution) · **Trust:** T1, T6
- **Goal:** The canonical Reddit screenshot per the trade-reply doctrine (NORTH_STAR Distribution): a side-by-side trade comparison card — players/picks on each side, valued under a league's settings, key assumptions visible — exportable as image with Razzle colors and "razzle.lol" watermark. Plus plain watermarked export for screener/workbench views.
- **Scope:** to be fenced before activation (likely `/og/*` server-rendered routes + a compare view).
- **Gates:** to be defined when fenced; G5 must include: the card alone answers "who wins this trade?" without the reader needing the app.

### S-008 deploy [OPEN]
- **Pillar/Layer:** Infrastructure (launch gate) · **Trust:** —
- **Goal:** Fly.io API + web live on razzle.lol behind Cloudflare; weekly sync cron; founder provides DNS + keys.
- **Scope:** to be fenced before activation.
- **Gates:** to be defined when fenced.

> Post-launch queue (do not start before 2026-07-28 unless launch path is done): valuation model layers (positional age curves, team situation surplus/deficit, growth rates — the NORTH_STAR build sheet), consensus market values beside intrinsic values, Bureau Self-Scout + monitoring/prediction, Monte Carlo championship odds, injury intel feed + Dolphin timelines + champ-probability deltas, Situation Room ask flow, Stripe Pro tier.

## LEDGER

| Slice | Date | Commit | Gates | Note |
|-------|------|--------|-------|------|
| seed | 2026-06-09 | — | G1–G4 | Repo seeded: specs, factory, domain spine (scoring+VORP), tokens, personas, web skeleton |
| S-001 | 2026-06-09 | (this) | G1–G5 | nflverse adapter + sync CLI; 8364 players, 11891 week rows (2024–2025), idempotent, db 1.6MB; GET /api/players live |
| S-002 | 2026-06-13 | 78996ad | G1–G5 | screener API + web UI; position filter, sortable columns (whitelist-guarded), nuqs URL state, position-color badges, "pulling film..." loading, design warm + chunky; 24 tests pass |
| S-003 | 2026-06-13 | (just pushed) | G1–G5 | player sheet hub; `/player/[gsis_id]` with season picker, stat table, prev/next nav via adjacent endpoint; Explore rows now link here; position-color badge, clean stat display; 29 tests pass |
| S-004 | 2026-06-13 | (just pushed) | G1–G5 | scoring presets (Standard/PPR/Half/TEP) + custom rules picker; fantasy-points column computed server-side via score_week; nuqs URL state; Player Sheet inherits scoring_preset (T3 hallway); McCaffrey PPR=416.6 pts vs Standard=314.6 (102 rec delta correct); 36 tests pass |
