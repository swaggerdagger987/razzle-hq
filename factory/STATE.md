# State

## NOW

- **Mode:** Milestone Zero refit landed 2026-07-22 — backlog below is a **swarm wave plan** (`factory/ROUTING.md` Swarm runs). Founder says **"swarm"** to launch; "start" still runs it serially.
- **Active slice:** none — W0 (S-009/S-010/S-011, architect seat) is next and unblocks the fleet.
- **Milestone Zero:** the perfect localhost, zero credentials (`spec/NORTH_STAR.md`). Every source in `spec/DATA.md` is keyless and was probed live 2026-07-22 — **no client deliverables block this milestone.**
- **Launch deadline:** **2026-07-28** (unchanged; Milestone Zero is the gate before deploy).
- **Blockers:** none. `CLIENT:` asks (Stripe keys, DNS, LLM keys) are all post-Milestone-Zero by design.
- **Last commit:** factory refit — T0 accuracy law, 18-source data stack, chart standard, swarm routing.
- **Date:** 2026-07-22

## THE 12-HOUR MAP (swarm run, ~35 fleet seats + 1 architect)

| Hours | Wave | Seats | What lands |
|-------|------|-------|-----------|
| 0–2 | **W0 foundation** | architect, sequential | All migrations, final-form main.py + web shell, registries, chart kit, tier switcher, crosswalk, verify harness |
| 2–6 | **W1 data + core** | ~14 parallel | Ten ingest adapters, screener, player sheet v0, sleeper connect, tier gating |
| 6–10 | **W2 product** | ~15 parallel | Custom scoring, workbench, ten Lab panels, player-sheet depth (usage/health/value), Bureau v0, explore density, compare view |
| 10–12 | **W3 trust** | ~7 + analysts | Trade answer card, accuracy audit fleet, design QA fleet, hallway audit, graveyard quarry, Room shell (stretch) |

Wave discipline: fences never overlap (isolation law); architect merges and gates per wave; cards below marked **[detail at wave start]** get their full build sheet from the architect just-in-time (`factory/SLICE.md`).

## BACKLOG

### ═══ W0 — FOUNDATION (architect seat, sequential) ═══

### S-009 foundation-db-api [OPEN — next]
- **Pillar/Layer:** Infrastructure (swarm prerequisite) · **Trust:** T0 substrate
- **Goal:** One migration (0002) creates every planned table; `main.py` reaches final form with all routers pre-registered; `sync_data.py` becomes a lazy-import adapter registry.
- **Scope fence:** `apps/api/migrations/versions/0002_*.py` · `apps/api/src/razzle_api/api/routers/` (empty routers: screener, player, lab, bureau, league, values, me) · `main.py` (final form) · `scripts/sync_data.py` (registry refit; existing nflverse adapter becomes registry entry #1) · `apps/api/src/razzle_api/ingest/report.py` (`SyncReport`).
- **Tables (0002):** `player_ids` (crosswalk) · `player_meta` · `snap_counts_week` · `injuries_week` · `depth_charts_week` · `games` · `ngs_passing_week` / `ngs_receiving_week` / `ngs_rushing_week` · `pfr_adv_week` (type-discriminated) · `ftn_week` · `qbr_week` · `contracts` · `draft_picks` · `combine` · `market_values` · `college_season_stats` · `leagues` · `source_syncs`. Column lists finalized by the architect from the source CSVs headers at implementation time (`spec/DATA.md` owns source truth).
- **Gates:** G1–G4; G5: fresh-db migrate exits 0; `--quick` sync still green; every pre-registered router serves a typed 501 or empty-state response, never 404.

### S-010 foundation-web-shell [OPEN]
- **Pillar/Layer:** Infrastructure (swarm prerequisite) · **Trust:** T3/T6 substrate
- **Goal:** Final-form shell: nav with all planned routes, providers (TanStack Query + nuqs), panel registry (all Launch-10 slugs from `spec/PRODUCT.md`), entitlement hook + tier switcher, the chart kit per `spec/DESIGN.md` Charts.
- **Scope fence:** `apps/web/src/app/layout.tsx`, `providers.tsx`, nav component · `apps/web/src/features/chart-kit/` · `apps/web/src/features/shell/` (nav, tier switcher, context bar placeholder) · `apps/web/src/features/entitlements/` (useEntitlement, `<Gated>` lock component) · panel registry module · route stubs (`/explore`, `/player/[gsis_id]`, `/lab`, `/lab/[panel]`, `/bureau`, `/compare`) each rendering a staff-voiced empty state — never a 404, never a dead end.
- **Deps added here once for the whole swarm:** `@tanstack/react-query@^5`, `@tanstack/react-table@^8`, `nuqs@^2`, `recharts@^3` (+ committed `pnpm-lock.yaml`).
- **Gates:** G1–G4; G5: every route renders shell + empty state; tier switcher flips a visible badge; chart kit renders a demo config in all states (loading/empty/data); voice grep clean.

### S-011 crosswalk-entitlements-verify [OPEN]
- **Pillar/Layer:** Data/Infrastructure · **Trust:** T0, T7
- **Goal:** Identity + tiers + accuracy harness: `player_ids` crosswalk synced (DynastyProcess `db_playerids.csv` + Sleeper dump enrich), `player_meta` filled, entitlement registry + seeded dev users (`dev-free`, `dev-pro`, `dev-elite`) + `GET /api/me` honoring the dev-tier cookie, and `scripts/verify_data.py` (G6 harness v1 covering players + week stats + crosswalk).
- **Scope fence:** `ingest/crosswalk.py`, `ingest/sleeper_players.py` · `domain/entitlements.py` (pure: feature key → minimum tier) · `services/me_service.py`, `api/routers/me.py` fill · `scripts/verify_data.py` · tests.
- **Gates:** G1–G4, G6 (self-hosting: the harness passes on synced data); G5: `/api/me` returns tier by cookie; crosswalk resolves ≥95% of QB/RB/WR/TE actives to sleeper_id, unresolved rows logged.

### ═══ W1 — DATA FLEET (one seat per card, parallel) ═══

All W1 ingest cards share the pattern: **fence = own module in `ingest/` + own tests + one registry row**; identity resolves through the crosswalk; idempotent upserts; `SyncReport` printed; G6 sample replay green. Sources/URLs/pitfalls: `spec/DATA.md`. **[detail at wave start]** unless noted.

### S-012 ingest-snap-counts [OPEN] — snaps + snap% per week; joins Explore + Player Sheet usage. T0/T1.
### S-013 ingest-injuries-depth [OPEN] — weekly injury reports + depth charts; Dolphin substrate. T0/T1.
### S-014 ingest-schedules-vegas [OPEN] — nfldata games.csv: schedule, results, spread/total; context substrate. T0/T2.
### S-015 ingest-ngs [OPEN] — combined NGS files (passing/receiving/rushing) filtered to synced seasons. T0/T1.
### S-016 ingest-pfr-adv [OPEN] — advstats week files (pass/rush/rec/def): pressures, broken tackles, drops. T0/T1.
### S-017 ingest-ftn [OPEN] — charting 2022+: routes vs man/zone, play action, screens. T0/T1.
### S-018 ingest-pedigree [OPEN] — contracts (.gz), draft picks, combine; the "expiring contract" thesis fuel. T0/T1.
### S-019 ingest-market-values [OPEN] — FantasyCalc API (formats × dynasty/redraft) + DynastyProcess weekly; stamped `market_values` rows. T0/T1 — **the market half of the valuation thesis.**
### S-020 ingest-college [OPEN] — cfbfastR seasons 2023–2025 into `college_season_stats`. T0.
### S-021 ingest-qbr [OPEN] — ESPN QBR weekly. T0. (Smallest card — good first fleet seat to validate the pattern.)

### ═══ W1 — CORE SURFACES (parallel with data fleet) ═══

### S-002 explore-screener [OPEN — execution-ready]
- **Pillar/Layer:** Explore L0–L1 · **Trust:** T1, T6
- **Goal:** `/explore` — season-total screener over real synced data: position filter, sortable columns, nuqs URL state, position colors, "pulling film..." loading state.
- **File plan:**
  - NEW `apps/api/src/razzle_api/services/screener_service.py` — `list_season_totals(...)` (the aggregation query).
  - NEW `apps/api/src/razzle_api/api/routers/screener.py` + `api/schemas/screener.py`.
  - EDIT `apps/api/src/razzle_api/main.py` — one import + one `include_router` line. *(W0 note: pre-registered — this edit disappears; fill the empty router instead.)*
  - NEW `apps/api/tests/integration/test_screener_api.py`.
  - EDIT `apps/web/package.json` — add deps `@tanstack/react-query@^5`, `@tanstack/react-table@^8`, `nuqs@^2`; run `pnpm install` and COMMIT `pnpm-lock.yaml` (CI uses `--frozen-lockfile`). *(W0 note: landed in S-010 — skip.)*
  - NEW `apps/web/src/app/providers.tsx` — client component: `QueryClientProvider` + `NuqsAdapter` (from `nuqs/adapters/next/app`). *(W0 note: landed in S-010 — skip.)*
  - EDIT `apps/web/src/app/layout.tsx` — wrap `{children}` in `<Providers>`. *(W0 note: landed in S-010 — skip.)*
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
  - Hallway: header links back to `/` and to `/scoring` (`crossRoomLinkPresent`); player-row → Player Sheet link lands with S-003 (route exists from W0 — link rows now).
- **Test plan (`test_screener_api.py`, reuse the `session_factory` + dependency-override pattern from `test_players_api.py`):** seed 2 RBs + 1 QB with 2 weeks each of 2024 stats → `season totals are summed and games counted` (known player: rush_yd = wk1+wk2, games = 2) · `sort=rush_yd&dir=desc orders correctly` · `position=RB returns only RBs` and `total` matches · `sort=evil_column returns 422` · `position=K returns 422` · `season with no rows returns empty rows, total 0, not 500`.
- **Gates:** G1–G4; G5 (paste outputs in commit body):
  - `curl -s 'localhost:8000/api/screener?season=2025&position=RB&sort=rush_yd&dir=desc&limit=50' | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['rows']), d['rows'][0]['name'])"` → `50 <a real RB1>` against the synced db
  - rush_yd of row[0] ≥ row[1] ≥ row[2] (paste first three)
  - `/explore` renders ≥20 rows; clicking a header or position pill updates the URL; hard refresh on that URL preserves the exact view; no 500s in API log
  - voice check: `grep -rEn '\bAI\b|powered by|chatbot|LLM' apps/web/src --include='*.tsx'` → no user-facing hits
  - screenshot of `/explore?position=RB&sort=rush_yd&dir=desc` attached to the session (sand bg, chunky border, RB teal badges) — would r/DynastyFF screenshot it?
- **Out of scope:** fantasy-points column and scoring presets (S-004) · virtualization, 100+ columns, college toggle (S-028) · saved views, export, watermark · pagination UI beyond limit/offset params · any new table or migration.
- **Pitfalls:** nuqs v2 throws without `NuqsAdapter` mounted above any `useQueryState` call · keep `page.tsx` a server component and the panel `"use client"` (nuqs + TanStack hooks are client-only) · TanStack Table v8 column defs must be memoized (`useMemo`) or the table re-mounts every render · SQLite `SUM` returns NULL for no rows — wrap aggregates in `COALESCE(..., 0)` or coerce in the service · sort param goes through a whitelist dict to a column object, never string-interpolated into SQL · CI runs `pnpm install --frozen-lockfile`: forgetting to commit the updated `pnpm-lock.yaml` fails the web job.

### S-003 player-sheet-v0 [OPEN] **[detail at wave start]**
- **Pillar/Layer:** Player Sheet L0–L1 · **Trust:** T3
- **Goal:** `/player/[gsis_id]` — position-colored header (name, team, meta from `player_meta`, headshot), season totals + weekly gamelog table, prev/next player switch, instant feel; every Explore row links here.
- **Fence:** `apps/web/src/features/player-sheet/` + `/player` page fill · `services/player_service.py` + player router fill · tests. Interface: `GET /api/player/{gsis_id}` → identity + meta + season totals + weekly rows.
- **Gates:** G1–G4, G6; G5: Explore row click lands here; switch feels instant; clean at 375px; hallway `playerIdentityConsistent`; screenshot.

### S-022 sleeper-connect [OPEN] **[detail at wave start]** *(was S-006)*
- **Pillar/Layer:** Bureau L0 · **Trust:** T2
- **Goal:** Sleeper username → league list → pick league; persist to `leagues` with `LeagueConfig` mapped from Sleeper `scoring_settings`; context bar shows `@user · league` on every route; screener/workbench default to the connected league's scoring. Keyless — works on localhost day one.
- **Fence:** `ingest/sleeper_league.py` · `services/league_service.py` + league router fill · `features/shell/` context-bar fill · connect flow UI · tests.
- **Gates:** G1–G4, G6 (roster identity via crosswalk); G5: connect a real username end-to-end on localhost; scoring settings match Sleeper's JSON field-for-field (T0 for league rules); hallway `leagueContextGlobal`.

### S-023 tier-gating [OPEN] **[detail at wave start]**
- **Pillar/Layer:** Infrastructure/Product · **Trust:** T7
- **Goal:** The paid line rendered: `<Gated feature="...">` lock treatments on Pro/Elite surfaces (chunky sticker lock, visible payoff copy, never an error page), tier badge in nav, switcher flips the whole product live.
- **Fence:** `features/entitlements/` fill (component states per tier) · gate placements on lab/bureau routes · tests.
- **Gates:** G1–G4; G5: browse `/lab` as dev-free (locked, inviting) vs dev-pro (open) vs dev-elite; screenshot each; voice grep clean.

### ═══ W2 — PRODUCT FLEET (parallel) ═══

### S-004 explore-custom-scoring [OPEN] **[detail at wave start]**
- **Pillar/Layer:** Explore L3 · **Trust:** T1, T2, T3
- **Goal:** Scoring preset picker (PPR/half/standard/TEP from `domain/scoring/presets.py`) + editable core rules; fantasy-points column computed server-side by `score_week` over real week stats; URL carries the config; connected league's scoring is the default preset.
- **Gates:** G1–G4; G5: points column changes when rules change; values match engine unit-test fixtures exactly (T0 for computed numbers); URL carries the preset.

### S-005 valuation-workbench-v0 [OPEN] **[detail at wave start]**
- **Pillar/Layer:** Lab L1–L3 (flagship; absorbs Launch-10 `vorp`) · **Trust:** T1, T5, T6
- **Goal:** `/lab/workbench` — the income approach made visible. VORP over a real season: assumptions panel (scoring config, replacement logic, league size) left, tier-colored value table right, live recompute, methodology note beside the numbers, **market value column beside intrinsic (from `market_values`) — the gap rendered as the trade thesis.** Octo header. Best-of-2 seats; architect picks on T6.
- **Gates:** G1–G4, G6; G5: real top-200 renders; position ranks match `test_vorp.py` logic; changing an assumption visibly moves values; market column sourced+stamped; links to Player Sheet; screenshot passes the r/DynastyFF test.

### S-024 lab-panels (ten seats, one per Launch-10 slug) [OPEN] **[detail at wave start]**
- **Pillar/Layer:** Lab L1–L2 · **Trust:** T1, T5, T6
- **Goal:** Each Launch-10 panel (`spec/PRODUCT.md` owns the list; `vorp` absorbed by S-005) rendered real: chart-kit visualization per its stated shape, staff-owner header, domain loading copy, Player Sheet links, watermark. One seat per slug, ten parallel — identical card template, different slug/data/chart config.
- **Fence per seat:** `features/lab/panels/<slug>.tsx` + its service/router fill + tests. Registry rows landed in W0.
- **Gates per seat:** G1–G4, G6; G5: panel renders real data in its stated shape (never JSON dump), gated per tier map, screenshot.

### S-025 player-sheet-usage [OPEN] **[detail at wave start]** — Hawkeye tab: snap%, targets/routes, NGS separation/aDOT, weekly usage chart (chart kit). T1/T3. G6.
### S-026 player-sheet-health [OPEN] **[detail at wave start]** — Dolphin tab: injury history timeline from `injuries_week`, current status, durability read. `dolphinReachable` satisfied product-wide. T1/T3. G6.
### S-027 player-sheet-value [OPEN] **[detail at wave start]** — market value (stamped source) beside intrinsic VORP under active scoring; the gap called out in Caveat; contract line (OTC) + pedigree. Links into workbench. T1/T3. G6.
### S-028 explore-density [OPEN] **[detail at wave start]** — Explore L1: column groups from new sources (snaps, NGS, adv, market), 100+ columns, TanStack Virtual, college toggle (blue mode). T1/T6. G6.
### S-029 bureau-v0 [OPEN] **[detail at wave start]** — league home after connect: standings + real points, power ranks, roster grades vs market values, "who's hoarding RBs" reads, weekly briefing card v0 — all deterministic from synced + Sleeper data (no LLM). Bureau summary free, deep-dive Pro-gated. T2/T4/T6.
### S-030 compare-view [OPEN] **[detail at wave start]** — `/compare?a=...&b=...`: side-by-side players (+picks later) under active league settings, assumptions visible; the pre-export trade answer surface. T1/T6.

### ═══ W3 — TRUST FLEET (parallel) ═══

### S-007 trade-answer-card [OPEN] **[detail at wave start]**
- **Pillar/Layer:** Distribution · **Trust:** T1, T6
- **Goal:** The canonical Reddit screenshot per the trade-reply doctrine: compare view exported as image — players/picks each side, valued under the asker's settings, assumptions visible, Razzle colors, `razzle.lol` watermark. Plus plain watermarked export for screener/workbench. G5 law: the card alone answers "who wins this trade?" without the app.
### S-031 accuracy-audit [OPEN] — analyst fleet: full G6 across every synced source at high sample count; every mismatch fixed or documented as a source discrepancy; report in commit body. **Milestone Zero cannot pass without this card green.** T0.
### S-032 design-qa [OPEN] — analyst fleet: screenshot every route in both themes at 1440/375, audit against `spec/DESIGN.md` Do/Don't + chart standard, fix loop. T6.
### S-033 hallway-audit [OPEN] — the `spec/PRODUCT.md` wiring checklist across all routes: `playerIdentityConsistent`, `leagueContextGlobal`, `crossRoomLinkPresent`, `staffRegistryAligned`, `dolphinReachable` + voice grep repo-wide. T3.
### S-034 graveyard-quarry [OPEN] — audit `graveyard/` (razzle, razzle-legacy, FDL) for anything valuable not yet carried in (pixel-room canvas assets, adapter edge cases, panel ideas, persona copy); report + ≤3 proposed cards. Read-only quarry rules apply.
### S-035 room-shell [OPEN — STRETCH] — Situation Room L0 without LLM keys: dark floor (`--bg-ink`), six staff present, deterministic briefing cards from real data (injury flag → Dolphin card with timeline from `injuries_week`). Ask flow stays behind the entitlement flag until keys arrive (post-Milestone-Zero). T4.

> **Post-Milestone-Zero queue (do not start):** S-008 deploy (Fly.io + razzle.lol + cron) · Stripe Pro tier · LLM keys → Room asks + staff nudges (OpenRouter BYOK) · valuation model layers (age curves, team situation, growth rates) · Monte Carlo championship odds · Bureau monitoring/prediction · OG share routes.

## LEDGER

| Slice | Date | Commit | Gates | Note |
|-------|------|--------|-------|------|
| seed | 2026-06-09 | — | G1–G4 | Repo seeded: specs, factory, domain spine (scoring+VORP), tokens, personas, web skeleton |
| S-001 | 2026-06-09 | (prior) | G1–G5 | nflverse adapter + sync CLI; 8364 players, 11891 week rows (2024–2025), idempotent, db 1.6MB; GET /api/players live |
| refit | 2026-07-22 | (this) | G1–G4 | Milestone Zero refit: T0 accuracy law + G6, 18-source data stack, chart standard, swarm routing, wave backlog. Verified live: tests 18 pass, web build green, --quick sync green, all 18 sources HTTP 200 keyless |
