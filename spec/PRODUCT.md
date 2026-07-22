# Product — Three Rooms, One Case File, One Context Engine

**Rule: depth before breadth, through the hallway.** One vertical slice per lease, wired into the rest of the product. A deep panel that dead-ends is a silo, and silos are VETO.

Room names are user-facing; internal code keeps stable names (routers, features) so recovered work doesn't churn. Routes: `/scratchpad` · `/line` · `/war-room` · `/player/[gsis_id]`.

## The core loop (what every slice serves)

Connect Sleeper (your username → **your leagues only** — no demo-league surface; recorded league JSON lives exclusively in the test suite as cassettes) → `LeagueContextRevision` → Player Sheet → Scratchpad → The Line → War Room. The three journeys in `spec/NORTH_STAR.md` (trade, injury, post-Sunday) are the acceptance tests for the loop.

## Depth ladders (L0–L5 per surface)

Climb one layer at a time until it screenshots on r/DynastyFF. Never prune mid-vertical.

### Scratchpad — test the theory
**Ceiling:** the research bench. The free screener is its front layer — filter any stat, NFL + college in one universe, custom formulas, shareable URL. Above it: the **valuation workbench** — the income approach made manipulatable, every assumption exposed, market price beside intrinsic value — and trade construction.

| Layer | Means |
|-------|-------|
| L0 | Screener loads ≥20 players over real data, sort/filter, URL state, no 500 |
| L1 | Fantasy points under exact compiled league scoring; 100+ stat columns; position colors; virtualized table |
| L2 | Valuation workbench: VORP over real seasons, assumptions panel, tier-colored values, methodology note |
| L3 | Custom formulas + saved views; college toggle (blue mode) with career-arc bridge |
| L4 | Trade construction: build a package, see both sides valued under league settings |
| L5 | Staff margin notes on rows (Hawkeye usage flags, Dolphin health flags) |

**Instrument catalog (one registry, panel slugs):** `weekly` (Hawkeye, heatmap) · `prospects` (Hawkeye, scatter) · `dynasty-rankings` (Octo, tier table) · `trade-values` (Bones, chart) · `breakouts` (Hawkeye, table) · `gamelog` (Atlas, timeline) · `efficiency` (Octo, bar) · `aging-curves` (Octo, line) · `buy-sell` (Bones, cards) · workbench (Octo, flagship). Every instrument = chart-kit config + data, never bespoke chart code.

### The Line — see the consequences
**Ceiling:** league odds & leverage (fantasy context, never sportsbook picks). Connect once; every manager profiled, every roster simulated, every trade path scored. Reports without being asked.

| Layer | Means |
|-------|-------|
| L0 | Exact league state: standings (H2H **and median where the league plays it**), points, rosters — exactness before odds |
| L1 | Roster power + depth grades per manager, build profiles |
| L2 | Odds v0: labeled Monte Carlo (`model: line-v0`, sampling actual weekly distributions under compiled rules) — playoff and title odds with model + as-of visible |
| L3 | Scenario deltas: trade/injury overlays re-simmed; baseline vs scenario odds side by side |
| L4 | Manager pressure map: who's panicking, who's hoarding, exploit windows |
| L5 | The weekly Line Briefing — screenshot-native league report for the group chat (the league option's reason to exist) |

### War Room — make the call
**Ceiling:** the room already knows before you walk in. Evidence packet (player + league + scenario + freshness + calculations) → verdict with urgency tier. **Milestone Zero ships deterministic verdicts** (start/sit comparisons, trade delta + roster fit + rival-dominance check) with staff-voiced templated briefings; live model voices are a later integration that reuses the same packets. Never let any model invent facts the context layer lacks.

| Layer | Means |
|-------|-------|
| L0 | Ask → briefing card with urgency (URGENT / MONITOR / OPPORTUNITY / ROUTINE) |
| L1 | Evidence packet rendered: what we know, from where, as-of when |
| L2 | League + player + scenario context in every briefing; verdict names the tradeoff |
| L3 | All six staff routable; injury → Dolphin first |
| L4 | Cross-staff triggers (Dolphin flag → Hawkeye replacement-usage follow-up) |
| L5 | Pixel canvas + proactive nudges (post-Milestone-Zero; chat-only is scaffolding) |

### Player Sheet — the case file (first-class pillar, own ladder)
The connector of all rooms. Every player click anywhere resolves here, then branches out.

| Layer | Means |
|-------|-------|
| L0 | Land → switch players instantly; position-colored header; clean at 375px |
| L1 | Full stat history (weekly + season, **NFL 1999–present**), gamelog |
| L2 | **The career arc — the signature visualization:** college seasons (2014–) → combine + draft capital → pro seasons, one timeline under your scoring lens |
| L3 | League context: who owns him, whose roster needs him, your exposure; injury status + history (Dolphin) |
| L4 | Value module: intrinsic (your assumptions, link into workbench) beside market price (permissioned source, stamped) — the gap on every sheet |
| L5 | Value watches + trade-ideation hooks ("3 managers in your league need a TE") |

## The hallway — wiring checklist

Context that always crosses rooms: Sleeper user + league (context bar on every route) · open player (URL params) · active scenario (URL param, never mutates truth) · staff identity (one registry) · one context-block builder.

Every slice that ships a surface passes:

| Check | Meaning |
|-------|---------|
| `playerIdentityConsistent` | Click player anywhere → same Player Sheet |
| `leagueContextGlobal` | Connected league visible in context bar on every room |
| `provenanceVisible` | Numbers can reveal source + as-of; unsupported rules show the coverage chip |
| `crossRoomLinkPresent` | At least one typed link out — no dead ends |
| `staffRegistryAligned` | Staff ids/copy from the one registry |
| `dolphinReachable` | Surface shows player health → Dolphin is reachable |

**Wrong:** ship dynasty-rankings in isolation. **Right:** ship dynasty-rankings + Player Sheet link + league-aware row + Octo header + War Room prefill.

## Free / paid line

**Tiers gate depth and actionability, never truth.** Localhost: deterministic entitlement switcher (Free/Pro/Elite), one registry (feature key → minimum tier), `GET /api/me`; every gated surface renders its real gated state — visible payoff, chunky lock treatment — never an error page. Stripe later assigns tiers to real users; it adds nothing else.

| Tier | Experience |
|------|-----------|
| **Free** | Screener, Player Sheet facts + career arc, league overview, limited Scratchpad views |
| **Pro** | Full Scratchpad (workbench, assumptions, formulas), The Line deep dives + scenarios |
| **Elite** | Full War Room, richer scenario capacity, proactive/advanced intelligence |

## Explicitly deprioritized

V1's 76 HTML pages (never port horizontally) · ESPN/Yahoo import (post-Sleeper-plateau) · non-Reddit channels · auth/billing before decision trust · fake "live" medical/odds/market claims · 100 shallow panels before ten are excellent · browser/localStorage context bridges · legacy bridges or monolithic room files.
