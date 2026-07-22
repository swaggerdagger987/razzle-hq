# State

## NOW

- **Mode:** constitution locked 2026-07-22 — backlog below is the **stage plan to Milestone Zero** (`spec/NORTH_STAR.md`), run by the captain loop (`factory/ROUTING.md`). Founder ignites with **"go"**; **"continue"** resumes at a checkpoint.
- **Run lock:** no active run. If a captain starts and finds ACTIVE leases below, it resumes them from their cards — never parallel copies.
- **Checkpoint:** Stage 1 complete; Founder kernel walkthrough pending. Reply **"continue"** to begin the parallel Stage 2 room wave or redirect.
- **Milestone Zero:** the perfect localhost, zero credentials. Every source is keyless (verified live 2026-07-22) — **no CLIENT blockers exist on this path.**
- **Launch deadline:** **2026-07-28** (unchanged; Milestone Zero gates it).
- **Recovery source:** branch `origin/claude/jolly-turing-l4muhb` holds the S-002→S-004 train (screener, player sheet, custom scoring; +2,884 lines, forked from 199eba5, own ledger marked done 2026-06-13). **Recover, never blind-merge** — verified defects listed on R-02. `origin/claude/affectionate-dirac-vbnwzz` has nothing ahead of main; ignore.
- **Execution budget:** 12–14 execution hours across stages; cost governance per `factory/ROUTING.md` (pyramid audited at every checkpoint).
- **Date:** 2026-07-22

## STAGE 0 CHECKPOINT — RECOVERY & RELEASE SAFETY

- **Shipped:** R-01 restored root gates; R-02 recovered the three product commits (API, Scratchpad, Player Sheet, custom scoring) while rejecting stale factory/Ruff config, then rebuilt the verified accuracy, pagination, mobile-Pts, and scoring-context defects; R-03 added the read-only G6 source-replay harness.
- **Proof:** fresh migration + health green; 78 tests; Ruff check and 52-file format check green; web lint/build green (7 routes). Live nflverse replay: players 8,363/8,363, 2024 weeks 5,849/5,849, 2025 weeks 6,020/6,020; deterministic 25/25 DB↔source samples, exhaustive filter-leak checks, zero mismatches. Scratchpad four-preset replay, URL paging/context navigation, and 1440/375 screenshots passed.
- **Cost vs pyramid:** 17 Grok writer/auditor invocations, 3 CTO/Fable interventions, one continuous Sol captain. The harness lease's second failure escalated to CTO and was not sent to a third writer. Exact token percentages are not exposed in repo evidence; verify the dashboard before certifying the 70/20/10 target.
- **Asks:** Founder walks `/scratchpad` in the cloud remote desktop (Free surface + Player Sheet context). No CLIENT blockers or credentials needed.
- **Next:** on **"continue"**, Stage 1 starts with captain-serialized K-01, then frozen-contract K-02/K-03 lanes; R-03's `--require freshness` / `--require identity` make those handoffs mechanical.

## STAGE 1 CHECKPOINT — CONTEXT KERNEL

- **Shipped:** complete Milestone-Zero schema + provenance/freshness; fail-closed Sleeper rules compiler; hermetic keyless Sleeper client/cache/cassettes; canonical-spine identity crosswalk; immutable owned-league connect/refresh/revision API; `/connect` kernel demo screen.
- **Proof:** fresh migration + health; 252 tests; Ruff check/76-file format and web lint/build green (8 routes). Live sync: 8,363 players, 11,869 weekly rows, 13,170 crosswalk rows; G6 freshness + identity required PASS 25/25. Public live smoke: `fantasyfootballers` → owned `Sparty League` → 14-roster immutable revision, partial coverage with six unsupported rules, offline GET replay. Browser reload made exactly one revision GET and zero connect POSTs; 1440/375 revision screenshots passed.
- **Cost vs pyramid:** 41 Grok writer/auditor invocations across parallel compiler, Sleeper, crosswalk, context API and UI lanes; 3 CTO/Fable interventions for repeated T0/architecture failures; Sol retained serialized migration/registry/spec locks. Exact token percentages remain dashboard-only.
- **Asks:** no credentials or CLIENT blocker. Founder can type their own Sleeper username at `/connect` to walk their leagues; the public smoke account remains available for a reproducible proof.
- **Next:** on **"continue"**, run the six-lane Stage 2 wave (Player Sheet, Scratchpad workbench, Line, War Room, chart kit, tiers) against the now-frozen context/cassette contracts.

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

### R-03 verify-harness-v1 [DONE] · M · writer + auditors
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

### K-01 migrations-and-provenance [DONE] · L · **captain-authored** (serialized lock)
- **Pillar / Trust:** context-kernel infrastructure; T0 traceability and T2 shared league truth.
- **Goal:** one Alembic wave creates the complete Milestone-Zero schema; `main.py` reaches its final router registry; sync becomes lazy-adapter based and stamps freshness; one provenance envelope contract is ready for every room.
- **File plan:** NEW `apps/api/migrations/versions/0002_context_kernel_tables.py`, `apps/api/src/razzle_api/ingest/report.py`, `apps/api/src/razzle_api/core/provenance.py`, `apps/api/src/razzle_api/api/schemas/provenance.py`, router shells `api/routers/{context,me,scenarios,scratchpad,line,war_room,values}.py`, tests `unit/test_{provenance,sync_registry}.py` and `integration/test_router_preregistration.py`; EDIT `apps/api/src/razzle_api/main.py`, `apps/api/src/razzle_api/ingest/nflverse.py`, `scripts/sync_data.py`, `apps/api/tests/integration/test_migrations.py`, and narrowly `unit/test_verify_data.py` for a stamped freshness integration. No domain, web, package, spec, or other factory edits.
- **Schema identity/provenance:** `source_syncs(id,source,season,rows,fetched_at)` with separate partial unique indexes for global NULL-season and seasonal stamps; `player_ids(gsis_id PK,sleeper_id,espn_id,pfr_id,cfb_player_id,mfl_id,fantasycalc_id,name,merge_name,position,team)` with partial unique external ids and no FK to `players`; `player_meta(gsis_id PK/FK,birth_date,height_in,weight_lb,college,years_exp,jersey_number,status,headshot_url,as_of_season,as_of_week)`.
- **Schema kernel:** `leagues(league_id TEXT PK,sleeper_user_id,username,name,season,sport,total_rosters,created_at,updated_at)`; immutable `context_revisions(id TEXT PK,league_id FK,revision,compiled_rules_json,coverage_json,snapshot_json,sources_json,created_at)` unique `(league_id,revision)`; `scenarios(id TEXT PK,base_revision_id FK,kind,payload_json,label,created_at)` with kind CHECK `trade|injury_out|lineup_change|waiver`.
- **Schema data vessels:** `games` keyed `game_id` with season/week/teams/scores/rest/vegas; fantasy-player weeklies `snap_counts`, `injuries`, `depth_charts`, `ngs_week_stats`, `pfr_week_stats`, `ftn_week_stats`, `qbr_week_stats` use the source replay id plus `(player_id,season,week[,stat_type/game_type/slot])` natural uniqueness and FK to `players`; career/market tables `contracts`, `draft_picks(season,round,pick PK,gsis_id,pfr_player_id,cfb_player_id,player_name,position,college,age)`, `combine`, `market_values`, and `college_season_stats(cfb_player_id,season PK plus pass/rush/receive totals)`. JSON is TEXT, timestamps ISO UTC TEXT, counting stats FLOAT, and identity fields never coerce to zero.
- **Interfaces:** `SourceStamp(source,season,rows,fetched_at)` and `SyncReport(adapter,stamps,upserted,skipped,warnings)` frozen dataclasses; `nflverse.sync(session,seasons) -> SyncReport`; sole `ADAPTERS: dict[str,str]` in `sync_data.py` lazy-loads `sync`; `build_meta(*,revision=None,sources=(),coverage=None,assumptions=(),model_version=None) -> dict` validates `ProvenanceMeta` and omits unset model version.
- **Freshness contract:** nflverse stamps exact sources `nflverse_players` with SQL NULL season and `nflverse_week_stats` per season; `rows` equals mapped/upserted rows and one UTC as-of is shared by a run. Registry preserves `--quick`, `--seasons`, `--status`, existing print lines, idempotency, and one commit at end.
- **Router freeze:** keep all existing paths; pre-register context (`/api/context/connect`, `/leagues/{league_id}/refresh`, `/revision/{revision_id}`), `GET /api/me`, `POST /api/scenarios`, and empty `/api/{scratchpad,line,war-room,values}` shells. Unimplemented frozen paths return explicit 501, never 404; later writers fill their owned module without touching `main.py`.
- **Test plan:** all canonical tables/columns/indexes/constraints present; 0001 tables and rows survive upgrade/downgrade/re-upgrade; source NULL uniqueness and scenario CHECK; FK cascades; provenance serialization; lazy import and unknown adapter; repeat sync stamps update rather than duplicate; offline sync makes R-03 freshness required PASS; OpenAPI paths are registered and existing routes unchanged.
- **Gates:** G1–G4; G5 = fresh upgrade plus OpenAPI path assertions and 501 stubs; G6 after `sync_data.py --quick`: `verify_data.py --sample 25 --seed 20260722 --require freshness` exits 0.
- **Budget:** L, captain cap 80 turns; two S Grok auditors after integration.
- **Out of scope:** populating crosswalk/context, implementing stub bodies, new source adapters, changing existing player/week schema, FTN attribution, web, K-02 domain logic.
- **Pitfalls:** migrations/cross-cutting files are captain-only; SQLite NULL uniqueness needs partial indexes; `player_ids` cannot FK to the fantasy-only players spine; no ad-hoc DDL/autogenerate; source stamp rows are mapped counts, not raw counts; never weaken R-03 to pass.

### K-02 rules-compiler [DONE] · L · Grok writer + auditors
- **Pillar / Trust:** T0 fail-closed scoring and T1/T2 league-relative decisions.
- **Goal:** pure `compile_league(sleeper_json) -> CompiledRules` maps Sleeper scoring and league settings onto existing `LeagueConfig`, detects dynasty/redraft/keeper/best-ball, superflex, TE premium, median, playoffs and tiebreakers, and exposes honest coverage.
- **File plan:** NEW `domain/scoring/compiler.py`, `tests/unit/test_rules_compiler.py`, and cassettes `tests/fixtures/cassettes/sleeper_league_{tep_median_dynasty,standard_redraft}.json`; EDIT `domain/scoring/__init__.py` exports only. No network/DB/API/ingest/migration/main/shared fixtures.
- **Interfaces:** Pydantic `UnsupportedScoringKey(key,value,reason)`, `CoverageReport(status full|partial,supported_keys,unsupported_keys,ignored_zero_keys)`, `MatchupFormat(style h2h|h2h_median,median_enabled)`, `TiebreakerConfig(order,playoff_seed_type)`, and `CompiledRules(league_id,name,season,league,matchup,tiebreakers,te_premium,superflex,best_ball,coverage)`.
- **Scoring map:** support stored engine fields for passing/rushing/receiving two-points, first downs, 40-yard bonuses, fumbles, special teams, PAT/FG ranges, DST ranges, and `idp_*`; `bonus_rec_te` or consistent `rec_te-rec` sets TE premium. Transform Sleeper-exclusive yardage thresholds to the engine's stacking bonuses (`high delta = high points - low points`). Unknown nonzero or conflicting keys are sorted unsupported and make coverage partial; unknown zero keys are visibly ignored; missing keys do not erase engine defaults.
- **League detection:** `settings.type` 0/1/2 → redraft/keeper/dynasty; `best_ball=1` overrides format; SUPER_FLEX or two QB slots marks superflex; `league_average_match=1` marks median; roster positions compile counts; playoff, waiver, budget, deadline and league size map exactly; documented tiebreak order is record, points-for, points-against with raw seed type retained.
- **Test plan:** two cassette goldens; unsupported nonzero/zero; TE premium delta/conflict; two-QB superflex; best-ball/type map; exclusive bonus does not double-count through `score_week`; missing sections safe; module has no I/O imports.
- **Gates:** G1–G4; G5 = golden/coverage/bonus tests plus printed TEP dynasty `{coverage:full,matchup:h2h_median,format:dynasty}`; G6 not applicable.
- **Budget:** L, Grok High writer cap 80; two Grok Fast auditors.
- **Out of scope:** Sleeper HTTP/persistence, standings math, web chip, expanding engine for unsupported keys, migrations/shared locks.
- **Pitfalls:** `int` is DST interception, not pass INT; DST `fum_rec` only when DEF rostered; no silent unsupported nonzero; domain stays pure; never import graveyard.

### K-03a sleeper-client-cassettes [DONE] · M · Grok writer + auditors
- **Pillar / Trust:** T0 source honesty and T2 live-only league acquisition.
- **Goal:** keyless Sleeper client fetches one user's current-season leagues and complete league snapshots; the 14MB player dump uses a 24h disk cache; all CI league JSON is cassette-only.
- **File plan:** NEW `apps/api/src/razzle_api/ingest/sleeper.py`, `tests/unit/test_sleeper_client.py`, and trimmed files under `tests/fixtures/cassettes/sleeper/` for state, user, leagues, league, users, rosters, traded picks, and per-week matchup/transaction responses. No DB/router/service/domain/main/sync/migration/shared locks.
- **Interfaces:** `sleeper_get(path,timeout=30)`, `fetch_nfl_state`, `fetch_user`, `fetch_user_leagues`, `fetch_league`, `fetch_rosters`, `fetch_users`, `fetch_matchups`, `fetch_transactions`, `fetch_traded_picks`, `fetch_league_snapshot`, and `get_players_nfl(force_refresh=False,cache_dir=None)`; urllib with `User-Agent: razzle-sync/1.0`, JSON errors typed as `SleeperUpstreamError`.
- **Data contract:** season is `state.league_season`; leagues endpoint uses returned user id; snapshot contains league/users/rosters/traded picks, matchups weeks 1..display week (bounded 1..18), transactions weeks 0..18, and state. Players cache is `data/cache/sleeper_players_nfl.json` plus UTC metadata; fresh valid cache skips network, stale/corrupt/forced cache refetches atomically. Connect itself never needs the dump.
- **Test plan:** exact URL graph and ownership inputs; unknown user; upstream HTTP/timeout/invalid JSON; complete snapshot; fresh/stale/corrupt/forced cache; cassette transport proves pytest never reaches public Sleeper; no committed full dump or non-cassette league JSON.
- **Gates:** G1–G4; G5 = cassette snapshot assertions and cache replay with network blocked; G6 not applicable.
- **Budget:** M, Grok High writer cap 40; two Grok Fast auditors.
- **Out of scope:** DB writes/crosswalk/context API/compiler/web/live credential flow.
- **Pitfalls:** live product only but tests never live; 24h cache under gitignored data only; use Sleeper state season, not calendar year; no demo league or graveyard import.

### K-03b context-and-crosswalk [DONE] · L · Grok writer + auditors · after K-01, K-02, K-03a
- **Pillar / Trust:** T0 identity substrate and T2 immutable shared league context.
- **Goal:** canonical spine seed + DynastyProcess + Sleeper builds `player_ids` with `player_ids ⊇ players`; username returns only their leagues; refresh persists a new immutable revision with snapshot, compiled rules, coverage and provenance; revision reads are offline.
- **File plan:** NEW `ingest/crosswalk.py`, `services/context_service.py`, `api/schemas/context.py`, unit tests for crosswalk/service, integration `test_context_api.py`, and trimmed crosswalk fixtures; EDIT the K-01-owned router shell `api/routers/context.py` only. Captain adds the sole crosswalk registry row between waves, ordered after nflverse. No migrations/main/sync script/core/domain/web.
- **Interfaces/API:** `connect_username(session,username)`, `refresh_league(session,league_id,username)`, `get_revision(session,revision_id)`; `POST /api/context/connect {"username"}` → user/current season/their league summaries/meta; `POST /api/context/leagues/{id}/refresh {"username"}` rechecks ownership then returns new revision; `GET /api/context/revision/{id}` returns the stored response with no network. Unknown user/revision 404, foreign league 403, upstream failure 502.
- **Crosswalk:** three deterministic layers, exact keys only. (0) Spine seed: every `players` row upserts `player_ids(gsis_id,name,position,team)`; conflict touches only those fields; empty `players` is exit 2. (1) DynastyProcess overlays by exact `gsis_id`: fills external ids + merge name; NA/blank → NULL; conflicting duplicate gsis rows skip visibly; an external id claimed by multiple gsis ids is withheld from all and logged; nflverse name/position/team win on spine rows, with DP drift warned; DP-only resolved rows insert, nameless rows skip. (2) Sleeper enriches by exact gsis and sleeper-id joins, NULL-fill only, never by name; gsis→multiple-sleeper conflicts are withheld and logged. Overlays never delete/blank stubs. Stamp accepted `dynastyprocess_playerids` and applied `sleeper_players`; spine provenance remains `nflverse_players`.
- **Revision contract:** persist canonical league identity plus JSON snapshot of users, rosters, matchups, transactions, traded picks and state; call K-02 `compile_league`, store compiled/coverage separately, call K-01 `build_meta`; each refresh increments revision and inserts, never updates old rows. Coverage partial still returns 200 and remains visible.
- **Test plan:** connect empty/owned leagues; ownership fence; two refreshes remain distinct; complete cassette snapshot; partial coverage passthrough; revision GET performs no HTTP; upstream errors; crosswalk happy/NA/no-gsis/conflict/enrich-only; source stamps; no live network; spine-coverage invariant; stub survival under DP conflict; external-id collision withholding; DP name drift warns without overwrite; crosswalk-before-players exit 2; idempotent rerun.
- **Gates:** G1–G4; G5 = cassette connect→refresh→GET and one live Founder username curl showing rules+coverage; G6 after crosswalk sync: verifier with both `--require freshness --require identity` exits 0.
- **Budget:** L, Grok High writer cap 80; three Grok Fast auditors.
- **Out of scope:** UI/context bar, auth, scenarios, standings/odds, multi-season history, name matching, full player dump in git.
- **Pitfalls:** K-01 schema/module names are frozen; K-03b starts only after dependencies merge; every refresh rechecks user leagues; cassettes are the only committed league JSON; no partial revision on upstream failure.
- **Stage-end freeze:** these three context endpoints, provenance envelope, compiled coverage shape, `GET /api/me` stub, and `POST /api/scenarios` stub. Kernel demo = Founder username → their league → revision with compiled rules + coverage.

### K-04 kernel-demo-surface [DONE] · M · Grok writer + auditors
- **Pillar / Trust:** T1/T2 context holy moment and T6 warm, screenshot-readable proof.
- **Goal:** a localhost screen lets the Founder enter a Sleeper username, see only that user's current leagues, choose one, create an immutable revision, and visibly inspect format/rules/coverage/source freshness.
- **File plan:** NEW `apps/web/src/app/connect/page.tsx`, `apps/web/src/features/context-kernel/{api,ContextKernelDemo}.ts{x,}`; EDIT `apps/web/src/app/page.tsx` for one Connect Sleeper entry. No API/schema/root provider/package/token/factory/spec changes.
- **Interfaces:** consume frozen `POST /api/context/connect`, `POST /api/context/leagues/{id}/refresh`, `GET /api/context/revision/{id}` via typed client functions. URL state uses `username`, `league_id`, and `revision`; refresh with a revision reloads from GET without refetching Sleeper.
- **Surface:** username form; owned-league cards; explicit loading/error/empty states; selected revision card showing league name/season, dynasty|redraft, superflex, TEP, H2H|median, playoffs, coverage full|partial, unsupported keys, revision id, sources/as-of, and a typed Scratchpad link. Token-only sand/chunky styling, 1440/375, no user-facing AI copy.
- **Test plan:** client rejects non-2xx with status/detail; TypeScript consumes frozen models without `any`; browser unknown-user error, empty leagues, multi-league selection, revision reload, partial-coverage display, and mobile layout. No localStorage/demo league/cassette mode in product.
- **Gates:** G1–G4; G5 = Founder username happy path on localhost plus screenshot at 1440/375; refresh URL retains revision and reload performs only GET. Until the Founder supplies a username, cassette-backed API integration plus browser error/loading states are the non-client proof.
- **Budget:** M, Grok High cap 40; two Grok Fast auditors.
- **Out of scope:** global context bar, auth/tier persistence, web standings/rooms, demo league data, changing frozen API.
- **Pitfalls:** live-only means no fake happy path; never expose raw JSON as the primary view; partial coverage is a warning chip, not a hidden success; user leagues are never searched globally.

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
| R-03 | 2026-07-22 | ce4b6a1…02f6601 | G1–G6 | Writer/Grok 4.5 High + Auditor/Grok 4.5 High Fast + CTO/Fable Max | M + audits + escalation | Read-only verifier; 22 focused / 78 total tests, deterministic bidirectional live replay, exhaustive filter leaks, capability handoff flags; two failed writer gates escalated to CTO |
| K-01 | 2026-07-22 | 48d94de + 31f291d | G1–G6 | Captain/Sol Max + Auditor/Grok 4.5 High Fast | L + 2S audits | 19-table kernel migration, frozen routers, lazy sync, provenance and freshness; 167 tests, migration roundtrip, live freshness required PASS |
| K-02 | 2026-07-22 | 572c5bf…7a6c473 | G1–G5 | Writer/Grok 4.5 High + Auditor/Grok 4.5 High Fast + CTO/Fable Max | L + audits + escalation | Pure Sleeper compiler, full/partial coverage, two league goldens, exact range/bonus boundaries; second failed audit escalated to CTO |
| K-03a | 2026-07-22 | 3ec683f + f033fe3 | G1–G5 | Writer/Grok 4.5 High + Auditor/Grok 4.5 High Fast | M + 4S audits | Keyless Sleeper graph, 30 synthetic cassettes, hermetic network tests, atomic 24h player cache; focused and full gates green |
| K-03b | 2026-07-22 | 162a337…e1017e7 | G1–G6 | 2 Writers/Grok 4.5 High + Auditors/Grok 4.5 High Fast + CTO/Fable Max | L + parallel sublease + audits | Canonical-spine crosswalk + immutable context API; 252 tests, typed contract, 13,170 ids, live identity/freshness 25/25 PASS |
| K-04 | 2026-07-22 | 8001923 + 69e7e36 | G1–G5 | Writer/Grok 4.5 High + Auditors/Grok 4.5 High Fast | M + 4S audits | `/connect` holy-moment UI; live owned-league revision, GET-only reload, partial coverage, 1440/375 screenshots, build/lint green |
