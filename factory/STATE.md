# State

## NOW

- **Mode:** constitution locked 2026-07-22 — backlog below is the **stage plan to Milestone Zero** (`spec/NORTH_STAR.md`), run by the captain loop (`factory/ROUTING.md`). Founder ignites with **"go"**; **"continue"** resumes at a checkpoint.
- **Run lock:** no active run. If a captain starts and finds ACTIVE leases below, it resumes them from their cards — never parallel copies.
- **Milestone Zero:** the perfect localhost, zero credentials. Every source is keyless (verified live 2026-07-22) — **no CLIENT blockers exist on this path.**
- **Launch deadline:** **2026-07-28** (unchanged; Milestone Zero gates it).
- **Recovery source:** branch `origin/claude/jolly-turing-l4muhb` holds the S-002→S-004 train (screener, player sheet, custom scoring; +2,884 lines, forked from 199eba5, own ledger marked done 2026-06-13). **Recover, never blind-merge** — verified defects listed on R-02. `origin/claude/affectionate-dirac-vbnwzz` has nothing ahead of main; ignore.
- **Execution budget:** 12–14 execution hours across stages; cost governance per `factory/ROUTING.md` (pyramid audited at every checkpoint).
- **Date:** 2026-07-22

## THE STAGE PLAN (dependency graph)

| Stage | Hours | Lanes | Founder checkpoint |
|-------|-------|-------|--------------------|
| **0 — Recovery & release safety** | 0–1.5 | 1 writer + 3–5 auditors | Recovery report: salvaged vs rebuilt |
| **1 — Context kernel** | 1.5–4 | 3 writers | Kernel demo: connect league → compiled rules + coverage on screen |
| **2 — Case file + three doors v0** | 4–7.5 | 5–6 writers + auditors | **CTO review, then:** walk three rooms per tier |
| **3 — Scenarios & closing the loop** | 7.5–11 | 4–6 writers | Three journeys replayed end-to-end |
| **4 — Trust pass** | 11–12.5 (+2 college-slip allowance) | audit fleet + S-class fixes | **CTO review, then:** founder walkthrough — Milestone Zero verdict |

Frozen contracts land at the end of Stage 1 (`/api/context/connect` · `/api/context/leagues/{id}/refresh` · `/api/context/revision/{id}` · the provenance envelope · `/api/me` · `POST /api/scenarios`). Web lanes build against cassettes until live swap at merge. Cards marked **[captain details at wave start]** get their full build sheet just-in-time (`factory/SLICE.md`); budget classes per `factory/ROUTING.md`.

## BACKLOG

### ═══ STAGE 0 — RECOVERY & RELEASE SAFETY ═══

### R-01 ci-scope-repair [DONE — landed in the constitution PR]
- graveyard/ excluded from pytest collection and ruff (pyproject.toml). Repo-root gates green again: 18 passed; all checks passed.

### R-02 recover-screener-train [DONE] · L · writer + auditors
- **Goal:** the jolly-turing S-002→S-004 train (screener, player sheet, custom scoring) recovered onto a lane branch, defects fixed, gated, merged — the free layer of Scratchpad live over real data.
- **Method:** reviewed cherry-pick from `origin/claude/jolly-turing-l4muhb` (merge-base 199eba5) — never blind merge. Its factory/* changes are superseded by this constitution; take product code + tests only.
- **Scope note:** the inherited card lacked a file plan; the captain fenced recovery to the three product commits' API/web/tests plus root router/provider/dependency wiring, then allowed only G5 audit fixes for pagination, mobile Pts visibility, custom-scoring honesty, and hallway links.
- **Verified defects to fix (read 2026-07-22):**
  1. `services/screener_service.py` `SCREENER_STAT_COLS` scores from a 13-column subset — **omits `pass_two_pt`/`rush_two_pt`/`rec_two_pt`, `pass_sack`, `fumble` (non-lost), `special_teams_td`**; any player with a two-point conversion scores wrong (a verified 2025 player differs by 2.0). Align the aggregation set with the engine fields the DB actually stores; the two-pt case becomes golden regression test #1.
  2. `sort=fantasy_points` loads every row into Python and sorts there — push into SQL or bound it; keep pagination `total` consistent.
  3. Scoring-context propagation: the Player Sheet must inherit the active scoring config (URL-carried), not silently fall back to standard.
- **Golden tests:** two hand-verified 2025 player-seasons per position (incl. one two-pt-conversion case and one non-REG-filter case), asserted to the decimal against `score_week` fixtures.
- **Gates:** G1–G6; G5: `/explore`-equivalent renders ≥20 real rows under PPR/half/standard/TEP with points matching goldens; URL round-trips; screenshot.

### R-03 verify-harness-v1 [OPEN — execution-ready] · M · writer + auditors
- **Pillar / Trust:** release safety; T0 accuracy law and reusable G6 substrate.
- **Goal:** `scripts/verify_data.py` map-replays deterministic random samples in both directions between `players` / `player_week_stats` and nflverse source rows, detects filter leaks and identity/stat mismatches, never mutates the DB, and exits 0 on a freshly synced database. Checks report `PASS`, `FAIL`, or visible `UNAVAILABLE(reason)`; `--require identity|freshness` promotes unavailable table-backed checks to failures.
- **File plan:** NEW `scripts/verify_data.py` (CLI, source loading, capability probes, report); NEW `apps/api/tests/unit/test_verify_data.py` (offline source fixtures built in `tmp_path`, temp migrated DB, no network). No edits to ingest, sync, migrations, domain, web, manifests, spec, or other factory files; `factory/STATE.md` remains captain-only for status/ledger.
- **Interfaces:** CLI `--sample N` (default 25), `--seed INT` (default 20260722), optional `--seasons`, `--database-url`, `--offline`, `--players-csv PATH`, repeatable `--week-csv SEASON=PATH`, repeatable `--require {identity,freshness}`, `--max-age-hours` (default 36), and `--json`. Core `verify(session, *, sample_size, seed, seasons, player_source_rows, week_source_rows_by_season, required_checks, max_age_hours) -> VerificationReport`; report/check dataclasses are importable by tests. Exit 0 = no FAIL (UNAVAILABLE allowed unless required), 1 = verification mismatch/empty surface/required check unavailable, 2 = usage, DB, or source I/O failure.
- **Data contract:** live mode calls existing `fetch_players()` once and `fetch_week_stats(season)` once per DB season; offline mode reads the supplied BOM-safe CSVs and forbids network. Reuse `map_player_row`, `map_week_row`, and `STAT_COLUMNS`; do not copy adapter formulas. Players key `gsis_id`; week key `(player_id, season, week)` with source season required to match the file/DB season. Compare player `gsis_id/name/position/team` exactly (`NULL` ↔ `None`, no fuzzy identity); compare every stored stat as a float with absolute tolerance `1e-9`. Report canonical-row SHA-256, source row count, fetched-at, and DB counts without claiming byte-level source hashes.
- **Checks:** sample N sorted DB keys and N mapped source keys with seeded `random.Random`; DB→source and source→DB must both match. Empty/undersized claimed surfaces, source-key conflicts, DB orphans, missing DB rows, wrong source season, POST/non-fantasy filter leaks, and week-player FK/position mismatches fail. Agreeing duplicate source rows are visible warnings; conflicting duplicates fail. Weekly team drift is not compared because the DB stores static latest team. Known adapter-zero fields (`return_*`, PAT/FG) are named in output, never presented as source-complete.
- **Capability probes:** `player_ids` missing or empty → `UNAVAILABLE identity (lands K-01/K-03)`; once populated, sampled `players.gsis_id` values must exist exactly. `source_syncs` missing → `UNAVAILABLE freshness (lands K-01)`; once the table exists, rows for `nflverse_players` and each synced `nflverse_week_stats` season must exist, match row counts, and be no older than `--max-age-hours`. Missing/incorrect columns or rows fail. Cross-source reconciliation remains visibly unavailable until a second source lands.
- **Test plan:** happy path exact replay; independent pinned expected maps for old/new nflverse columns and special-teams/two-point/fumble fields; stat corruption; player identity corruption; source→DB omission; DB orphan; wrong season; POST and K filter leaks; conflicting duplicate keys; NA→0 stats and nullable team; deterministic seed; undersized/empty surfaces; live fetch blocked in offline mode; HTTP/source error maps to exit 2; missing capabilities unavailable by default and fail under `--require`; fake populated capability tables exercise comparison code without DDL in the harness; row counts unchanged before/after.
- **Gates:** G1–G4. G5/G6: after `sync_data.py --quick`, `uv run python scripts/verify_data.py --sample 25 --seed 20260722` exits 0 with 25/25 players and 25/25 rows per present season in both directions, zero mismatches, canonical hashes, `UNAVAILABLE identity`, and `UNAVAILABLE freshness`; rerun produces the same sampled keys. `--require identity` and `--require freshness` each exit 1 on the Stage 0 schema. No live network runs inside pytest.
- **Budget:** M, writer cap 40 tool turns; two S auditors, 15 turns each.
- **Out of scope:** migrations; writes/stamps in `sync_data.py`; building `player_ids` or `source_syncs`; draft/college bridge; second-source reconciliation; other adapters; full-history mode; PBP return/kicking expansion; fixing discovered source-map gaps.
- **Pitfalls:** no ad-hoc DDL or Alembic call; verify is read-only. Do not use SQLite mtime as freshness, `ORDER BY RANDOM()`, name/team fallback, per-sample HTTP, skip-as-pass on enforced surfaces, `None == 0`, or season aggregates. Live source drift is a failure asking for re-sync, not tolerance. The mapper replay proves source→adapter→DB consistency; independently pinned test expectations prevent mapper bugs from becoming the sole oracle.

### ═══ STAGE 1 — CONTEXT KERNEL (after R-02, R-03) ═══

### K-01 migrations-and-provenance [OPEN] · L · **captain-authored** (serialized lock)
- **Goal:** one migration wave creates every planned table (`spec/DATA.md` canonical list: player_ids, player_meta, leagues, context_revisions, scenarios, source_syncs, games, snaps/injuries/depth/NGS/PFR/FTN/QBR weeklies, contracts, draft_picks, combine, market_values, college_season_stats); `main.py` reaches final form with all routers pre-registered (context, me, scenarios, player, scratchpad, line, war-room, values); `sync_data.py` becomes the lazy-import adapter registry; provenance envelope helper (`meta` builder) in `core/`.
- **Harness handoff:** G6 runs `verify_data.py --sample 25 --require freshness` (the rewritten sync must stamp `source_syncs`); K-03 additionally runs `--require identity` once the crosswalk is populated.

### K-02 rules-compiler [OPEN] · L **[captain details at wave start]**
- **Goal:** `compile_league(sleeper_json) → CompiledRules` — Sleeper `scoring_settings` → engine rules (superset already exists in `domain/scoring/`), format detection (dynasty/redraft, superflex, TE premium, **H2H vs H2H+median**, playoff weeks, tiebreakers), **fail-closed coverage report**. Pure domain; golden tests pin two known leagues (one TEP+median dynasty, one standard redraft). Unsupported nonzero keys → league *partial*, never silently scored.

### K-03 sleeper-context [OPEN] · L **[captain details at wave start]**
- **Goal:** live connect: username → **their leagues only** → league snapshot (rosters, matchups, transactions, picks, users) → `LeagueContextRevision` assembly + refresh; players-dump cache (24h, `data/cache/`); crosswalk build (DynastyProcess `db_playerids` + Sleeper dump → `player_ids`); cassettes recorded for tests (the only place league JSON is stored). Coverage chip data flows from K-02.
- **Stage-end freeze:** the context API contracts + envelope shape. Kernel demo = the Founder connects a real username on localhost and sees compiled rules + coverage.

### ═══ STAGE 2 — CASE FILE + THREE DOORS v0 (after Stage 1) ═══

All web lanes consume the frozen contracts; fences never overlap (isolation law). Tier gating uses the entitlement registry from H-06.

### H-01 player-sheet-v1 [OPEN] · M **[captain details at wave start]** — the case file: identity + meta header, full weekly/season history, ownership in connected league, injury status, links into all three rooms; career-arc section renders pro-side now (college segment arrives with C-05). Hallway: `playerIdentityConsistent`, `dolphinReachable`.
### H-02 scratchpad-workbench [OPEN] · M · **best-of-2** — recovered screener as the free layer + valuation workbench: VORP over real seasons under compiled rules, assumptions panel, tier-colored values, methodology note, market column (stamped source) beside intrinsic — the gap rendered.
### H-03 line-v0 [OPEN] · M — exact league state first: standings (**median included where played**), points, roster power, manager overview. No odds yet.
### H-04 war-room-v0 [OPEN] · L — evidence packet builder (player + league + freshness + calculations) + deterministic verdict engine (start/sit comparison; trade delta + roster fit + **rival-dominance check**) + staff-voiced templated briefing with urgency tiers. No LLM calls; packets are built to receive them later.
### H-05 chart-kit-and-canonical-viz [OPEN] · M — the kit (`features/chart-kit/`, sole Recharts import) + canonical five: dense table treatment, player trend, value distribution, trade delta, career-arc timeline shell (`spec/DESIGN.md` Charts).
### H-06 tiers-and-switcher [OPEN] · S — entitlement registry (feature → minimum tier per `spec/PRODUCT.md` table), `GET /api/me`, localhost switcher, chunky lock treatments. Browse the whole product as Free/Pro/Elite.

### ═══ STAGE 3 — SCENARIOS & CLOSING THE LOOP (after Stage 2) ═══

### C-01 scenario-engine [OPEN] · L — immutable overlays (`trade`, `injury_out`, `lineup_change`, `waiver`) on a base revision; engines accept `revision | scenario`; scenario id in URL; never mutates truth.
### C-02 line-odds-v0 [OPEN] · M — labeled Monte Carlo (`model: line-v0`): sample each roster's actual weekly distributions under compiled rules → playoff/title odds + **scenario deltas** (the "my RB is out, odds 30%→18%" moment). Model + as-of visible; backtested projections replace internals post-Milestone-Zero.
### C-03 trade-answer-card [OPEN] · M — the canonical screenshot: side-by-side players/picks under the asker's settings, assumptions visible, Razzle colors, `razzle.lol` watermark; export from compare view + workbench. G5 law: the card alone answers "who wins this trade?"
### C-04 history-backfill [OPEN] · M — NFL weekly **1999–2025** via `--full`; verify samples per decade; player sheet history extends automatically.
### C-05 college-bridge-and-career-arc [OPEN] · L — cfbfastR **2014–2025** ingest; keyed bridge via `draft_picks.cfb_player_id`; undrafted matching fails closed; career arc renders college → combine/draft → pro on the Player Sheet. Bridge coverage audited ≥95% of drafted actives since 2016. **The one card allowed to slip +2h rather than compromise accuracy.**
### C-06 journeys-e2e [OPEN] · M — the three journeys (trade, injury, post-Sunday) as replayable end-to-end tests over cassette leagues; these are Milestone Zero acceptance.
### C-07 data-density [OPEN] · M — remaining ingest lanes wired into surfaces: snaps + injuries + depth (usage/health tabs), schedules + vegas, NGS/PFR/FTN/QBR columns in Scratchpad, contracts + combine on the sheet, market_values refresh (FantasyCalc + DynastyProcess).

### ═══ STAGE 4 — TRUST PASS (after Stage 3) ═══

### T-01 accuracy-fleet [OPEN] · auditor fan-out + fixes — G6 at high sample count across every synced source + bridge; every mismatch fixed or visibly flagged; **Milestone Zero cannot pass without this green.**
### T-02 design-qa [OPEN] · auditor fan-out + S fixes — every route × tier × theme at 1440/375 vs `spec/DESIGN.md` Do/Don't + chart standard.
### T-03 hallway-audit [OPEN] · S — `spec/PRODUCT.md` wiring checklist on every route + repo-wide voice grep.
### T-04 demo-bootstrap [OPEN] · S — `scripts/demo.sh`: migrate + sync + boot both servers; founder walkthrough script in the checkpoint memo.
### T-05 graveyard-quarry [OPEN] · auditor — audit `graveyard/` (razzle, razzle-legacy, FDL) for anything valuable not carried (pixel War Room canvas assets, adapter edge cases, instrument ideas); report + ≤3 proposed cards. Read-only rules apply.

> **Post-Milestone-Zero queue (do not start):** deploy (Fly.io + razzle.lol + weekly cron) · Stripe Pro/Elite · LLM staff voices over War Room packets (OpenRouter, BYOK) · licensed projection/market feeds · odds backtesting + valuation model layers (age curves, team situation, growth) · pixel War Room canvas · proactive nudges · OG share routes · weekly Line Briefing for the league option.

## LEDGER

| Slice | Date | Commit | Gates | Seat/model | Cost | Note |
|-------|------|--------|-------|-----------|------|------|
| seed | 2026-06-09 | — | G1–G4 | — | — | Repo seeded: specs, factory, domain spine (scoring+VORP), tokens, personas, web skeleton |
| S-001 | 2026-06-09 | (prior) | G1–G5 | — | — | nflverse adapter + sync CLI; 8,363 players, 11,869 week rows (2024–25), idempotent, 1.6MB; GET /api/players live |
| R-01 | 2026-07-22 | (this PR) | G2, G4 | CTO/Fable | S | graveyard excluded from pytest+ruff; repo-root gates green (18 passed / all checks passed) |
| lock | 2026-07-22 | (this PR) | G1–G4 | CTO/Fable | — | Constitution: razzle.hq north star, context kernel, accuracy law, command structure + budgets, stage plan. Verified live: 18 sources keyless, NFL weekly 1999+, college 2014+, draft_picks bridge keyed, jolly-turing defects confirmed in code |
| R-02 | 2026-07-22 | 8811713 + 865c3f3 | G1–G6 | Writer/Grok 4.5 High + Auditor/Grok 4.5 High Fast | L + 6S audits | Recovered Scratchpad + Player Sheet; 56 passed, fresh migrate/health/build/lint green; eight 2025 goldens, four-preset live replay, URL paging/context browser replay, 1440/375 screenshots |
