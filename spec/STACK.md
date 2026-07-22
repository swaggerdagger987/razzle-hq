# Stack — Locked Architecture

Changing an entry here is frontier-model work (`factory/ROUTING.md`): write a short memo in the PR, add a dated row to the log below, update the narrative. Cheap-model sessions never touch this file.

## Layout

pnpm workspace (`apps/web`, `packages/*`) + uv workspace (`apps/api`). No turbo, no extra orchestration until two packages genuinely need it.

## Backend

- **FastAPI, Python 3.12, Pydantic v2.** One `APIRouter` per domain; routers stay thin — parse request, call service, return schema.
- **Domain purity (absorbed ADR-0004 "scoring as spine"):** `apps/api/src/razzle_api/domain/` contains pure business logic only — no database, network, cache, or HTTP imports. All fantasy numbers flow through `LeagueConfig → ScoringEngine → ValuationEngine`. Scoring and valuation are deterministic and exhaustively tested; values are derived from stats + config, not stored snapshots.
- **No junk-drawer names (absorbed ADR-0005):** no `utils/`, `helpers/`, `tools/`, `misc/`. One exception: `core/` for cross-cutting infra (db, logging). Name files for what they own.
- **Sync SQLAlchemy.** Async adds greenlet complexity SQLite can't use. Revisit if a real concurrency need appears.

## Database — SQLite + Alembic

**Dated decision (2026-06-09), supersedes razzle-legacy ADR-0002 (Postgres):** one file, `data/razzle.db`, WAL mode when serving. Reasons: single-writer weekly-sync workload; target scale ~10k users reads-mostly; zero ops on a Fly volume; the prior repo ran Postgres ADRs and never wrote a row. **Alembic owns the schema** — every table change is a migration; ad-hoc `CREATE TABLE`/`ALTER TABLE` in app code is forbidden. Migration smoke test runs in CI. Escape hatch: if concurrent writes or JSONB-shaped queries genuinely hurt, swap to Postgres via a memo here; SQLAlchemy keeps the surface portable.

## Frontend

- **Next.js 15 App Router + TypeScript.** Server Components render OG share cards server-side; file-based routing maps to `/lab/[panel]`, Bureau drawers, Room modal.
- **Tailwind v4** consuming `packages/ui/tokens.css` via `@theme`. No per-page CSS sprawl.
- **TanStack Table v8 + Virtual** for the screener (headless — keeps the chunky aesthetic). **TanStack Query** for server state; explicit loading/error/empty states for every async flow.
- **nuqs** — URL is the source of truth for screener state. Shareable URLs are a product feature, not a nicety.
- **Zod** client-side; generate TS types from the FastAPI OpenAPI schema so the client never drifts.
- **Recharts (v3) behind the chart kit** — `apps/web/src/features/chart-kit/` is the only import site for the chart library; instruments declare data + config and the kit owns axes, tooltips, watermark, provenance margins, loading/empty states (`spec/DESIGN.md` Charts). Chosen for fleet velocity: declarative, ubiquitous, fully styleable to the chunky standard.

## Platform

| Concern | Choice | Notes |
|---------|--------|-------|
| Hosting | Fly.io (API + web), Cloudflare CDN | SQLite-on-volume is first-class; LiteFS if replication ever needed |
| Cache | HTTP `Cache-Control` + CDN edge | **No app-layer cache.** Data changes weekly. If one endpoint needs memoization: `functools.lru_cache` on a service function |
| Background work | Sync + FastAPI `BackgroundTasks` | Only jobs at this scale: weekly nflverse sync (cron), webhook handling. Real worker only when multi-step pipelines exist |
| Rate limiting | slowapi decorators | When endpoints go public |
| Auth | **Deferred — but tiers are not.** One entitlement registry (feature key → minimum tier), deterministic localhost tier switcher (Free/Pro/Elite), `GET /api/me`. A managed provider (Clerk-class) later maps real identities onto the same entitlements | Do NOT port V1's 1,305-line JWT file. New repo, no legacy users to migrate |
| Billing | Stripe Customer Portal + idempotent webhooks | No reconciliation loop. Free + Pro $79.99/yr at launch; monthly/Elite flagged off until PMF |
| LLM | OpenRouter, BYOK override per user | One key, all models |
| Observability | Sentry + PostHog | When deployed. No home-rolled analytics tables |

## Product gates (locked)

| Question | Default | Revisit when |
|----------|---------|--------------|
| First Scratchpad instruments | see `spec/PRODUCT.md` instrument catalog | After 100 paid users |
| First 3 staff live | Razzle, Octo, Bones | After Room ships and usage is real |
| Launch pricing | Ladder: Free · Pro ($9.99/mo, $79.99/yr) · Elite ($19.99/mo, $149.99/yr) · plus **League option** (whole-league access, any tier's features, priced per league — Founder sets price when it ships). Rollout order: Free at launch → Pro when Stripe lands → Elite + League option in-season with the Bureau Briefing | After first 100 paid users |
| League import | Sleeper only | When Sleeper-only traffic plateaus |
| GTM | Reddit only | When Reddit MRR justifies expansion |

## Forbidden

- Importing from or bridging to the old repos (`swaggerdagger987/razzle`, `swaggerdagger987/razzle-legacy`). They are read-only reference quarries. No `legacy_bridge` pattern, ever.
- Duplicate registries: every catalog (panels, staff, columns) lives in exactly one place.
- Installed-but-unused infrastructure. If a dependency ships, a test exercises it.

## Decisions log

| Date | Decision | Notes |
|------|----------|-------|
| 2026-06-09 | All defaults above; SQLite over Postgres; sync SQLAlchemy; auth deferred to managed provider | Seed of razzle-hq. Absorbs razzle-legacy ADRs 0001–0005 and razzle DECISIONS.md |
| 2026-06-09 | **Valuation identity locked:** income approach, methodology published, assumptions user-adjustable; consensus market values shown for comparison, never sold as ours | Founder direction. See NORTH_STAR "valuation thesis" |
| 2026-06-09 | **Launch deadline July 28, 2026** — live and Reddit-shareable before draft season; scope bends, date doesn't | Founder direction, zero negotiation |
| 2026-06-09 | **Factory budget:** Claude subscription primary, $150 API credits overflow-only | See factory/ROUTING.md Budget |
| 2026-06-09 | **Pricing structure:** Free/Pro/Elite individual ladder stays; League option added as a purchase mode (whole-league access), not a replacement SKU. Rollout: Free → Pro → Elite + League in-season | Founder direction; supersedes the earlier "Free + Pro only" gate and the "league plan as second SKU" row |
| 2026-07-22 | **Milestone Zero:** perfect localhost with zero credentials before any integration work (Stripe, deploy, LLM keys) | Founder direction. See NORTH_STAR |
| 2026-07-22 | **razzle.hq structure:** Lab→Scratchpad (absorbs Explore), Bureau→The Line, Situation Room→War Room; Player Sheet = the case file; one `LeagueContextRevision` kernel, scenarios as immutable overlays | Founder direction + locked plan |
| 2026-07-22 | **T0 accuracy law + G6 gate:** zero silent errors, crosswalk identity, fail-closed rule coverage, provenance envelopes | Founder direction ("absolutely 0 mistakes on player accuracy") |
| 2026-07-22 | **Live Sleeper only in product** — username → your leagues; recorded cassettes exist only in tests. Demo-league surfaces rejected | Founder direction |
| 2026-07-22 | **Historical depth in scope:** NFL weekly 1999–2025; college 2014–2025; college→pro bridge keyed via draft_picks (`cfb_player_id`); career arc = Player Sheet signature viz. DB budget raised to <200MB | Founder direction ("how players went from college to pro") |
| 2026-07-22 | **Chart library locked: Recharts v3 behind one chart kit** — sole import site `features/chart-kit/` | Fleet velocity with zero design drift |
| 2026-07-22 | **Market sources: permissioned only** (FantasyCalc public API, DynastyProcess MIT); scraping proprietary sites forbidden; licensed feeds post-Milestone-Zero | Locked plan |
| 2026-07-22 | **Factory: CTO/captain/fleet command structure with leased budgets** — Fable Max CTO, GPT Sol Max captain, Grok 4.5 fleet | Founder direction. See `factory/ROUTING.md` |
