# North Star

**This document wins all arguments.** Every slice gets scored against it.

## The one number

**1,000 paid users.** During BUILD, chase the Trust Score (T0–T7) below. Everything else is a leading indicator.

**The one date: July 28, 2026.** The product is live and Reddit-shareable before draft season. Zero negotiation. Scope bends; the date does not.

**Milestone Zero (locked 2026-07-22): the perfect localhost.** The gate between here and the date. Everything the product *is* — the three rooms, the Player Sheet case file, real tiers, historical depth, established visualizations — exists and is flawless on localhost **with zero credentials**: no Stripe, no LLM keys, no deploy. Integrations decide who can reach the product; they never decide what it is. Work that only matters in production is out of scope until Milestone Zero passes. The Founder must be able to walk the finished product as any tier before a single external service is wired.

## The ambition

Complete domination of fantasy football intelligence. The market is small enough to fly under the radar and big enough that if the Razzle brand sticks, it compounds for a generation. We are not building a feature — we are building the place serious players think from: **the Moneyball moment for fantasy decisions**. Reddit subthreads are the entire distribution: keep giving real results to real players and the brand does the rest. (Positioning note: *we* may be described as AI-native; the product itself never says "AI" — `spec/VOICE.md`.)

## The thesis

**Razzle's superpower is not recommendations. It is removing the work required to make a recommendation specific.**

Today, getting decision-grade fantasy advice means feeding an LLM (or a friend) everything: your scoring, your rosters, whether it's dynasty or redraft, whether TEs get a premium, whether your league scores against the median as well as head-to-head, whether an otherwise fair trade makes one rival dominant. Nobody does that work, so all advice is generic. With Razzle, **you give it your Sleeper ID and the context work is done** — league rules, lineup slots, scoring, rosters, picks, matchups, standings, history, and this week's actual decision are already in the room before you ask.

The package: a fantasy football film room disguised as a Sunday comic strip. Warm sand, chunky borders, a Bengal tiger who doesn't hedge — and underneath, the kind of analysis that makes your leaguemate ask *"where did you get that?"*

> "Drake London saw 10 targets — three standard deviations above his baseline. That's why you lost."

That's Razzle. Not "consider monitoring your WR room."

## The core loop

**Connect Sleeper → versioned League Context → Player Sheet (the case file) → Scratchpad (test the theory) → The Line (see the consequences) → War Room (make the call).**

One league-context engine, three doors, one case file. Every room reads the same `LeagueContextRevision` (`spec/DATA.md`) — the rooms are different views over the same truth, never separate products stitched together. A **scenario** (a trade, an injury, a lineup change) is an immutable what-if overlay on that truth: it never mutates real league data, and every engine can run against truth or scenario.

**Three journeys prove the loop** (these are Milestone Zero acceptance, replayable end-to-end):

1. **Trade** — an offer arrives → inspect every asset through Player Sheets → stress-test assumptions in Scratchpad → re-sim both teams and the league in The Line → War Room delivers the verdict and why (including "fair value, but it makes your direct rival dominant — decline").
2. **Injury** — a star goes down → Player Sheet shows the verified status change → War Room says what to do now → The Line shows baseline vs injury scenario (your championship odds moved from 30% to 18%) → Scratchpad finds replacements and trade paths.
3. **Post-Sunday** — Scratchpad explains what happened (usage, opportunity, efficiency) → The Line shows standings and pressure shifts → War Room says what matters next week.

**The 15-second holy moment:** type a Sleeper username → pick your league → the War Room *already knows*: your exact scoring compiled (TE premium and median flagged on screen), your roster identified, this week's live question surfaced with the assumptions visible. You never told it anything but your username.

## The valuation thesis (the core differentiator)

**Fantasy points are cash flows.** KeepTradeCut and consensus rankings are the *market approach* — what the crowd will pay today. Razzle is the **income approach**: a player's value is built from explicit inputs and assumptions — usage, efficiency, age curve, contract situation, *your* league's scoring — that the user can see and manipulate.

- **We publish methodologies, never black-box values.** Every number comes with its assumptions exposed. Users stress-test, tweak an input, and watch the value move.
- **The model build sheet (none of it exotic — the edge is scalability + finance discipline):** current production baseline → positional age curve → team situation surplus/deficit → growth rate → translated through *your* league's scoring. Situational, per-player, per-league.
- Market price (consensus, from permissioned sources) is shown beside intrinsic value (yours) — **the gap IS the trade thesis.**
- **Trade intelligence is the wedge.** Converge stats → value players under your settings → make the trade with conviction.

Defensible precisely because it's transparent: anyone can copy a number, but a methodology users have stress-tested themselves becomes *their* methodology. That's trust.

## The three rooms + the case file

| Surface | Route | Job | Holy moment |
|---------|-------|-----|-------------|
| **Scratchpad** | `/scratchpad` | Test the theory. The free screener is its front layer (the forever-free acquisition surface), then custom formulas, the valuation workbench, trade construction. | Group chat says Player X is washed. You end the argument with one screenshot of your model. |
| **The Line** | `/line` | See the consequences. League odds & leverage: standings (median included), roster power, playoff paths, scenario deltas, manager pressure. | Your star RB goes down and The Line shows exactly how many championship points it cost you — and who in your league got stronger. |
| **War Room** | `/war-room` | Make the call. A context-aware briefing when you must act: start/sit, injury response, trade offer, waiver. Evidence packet in, verdict out, no hedging. | CMC goes down. Before you finish typing, the room tells you your title odds moved 30% → 18% — and what to do about it. |
| **Player Sheet** | `/player/[id]` | **The shared case file — not a fourth door.** Every player click anywhere resolves here, then branches into the three rooms. Career arc from college to pro, ownership in your league, health, usage, value vs market. | Land on a rookie and see his whole road: college production → combine → draft capital → pro usage, under your scoring. |

**If a feature doesn't make the Player Sheet more useful, it's probably a silo.** The Sheet is the connective tissue: Ja'Marr Chase gets hurt → War Room for what to do, The Line for how the league shifted, Scratchpad for the trade you can now make — all one click from his sheet.

## Data classes (never confuse them)

Every surface distinguishes: **Recorded** (official stats, rosters, transactions) · **Calculated** (exact points under your league's supported rules) · **Forecast** (projections/odds, always with model + version + as-of) · **Scenario** (immutable what-if overlays) · **Recommendation** (War Room advice built from the preceding evidence). Every important response exposes its context revision, source freshness, scoring coverage, and assumptions (`spec/DATA.md`).

## What we sell

**Trust.** Razzle wins when you trust it more than anything else for fantasy decisions. Because the numbers are **yours** (your scoring, your league, your picks), the staff already know your league, and the product looks like a toy but performs like a briefing room.

**Brand line:** *The Screener is forever free. The intelligence is what you pay for.* "Intelligence" = depth of understanding, never a model badge (`spec/VOICE.md`).

## Free vs paid

**Tiers gate depth and actionability, never truth.** All tiers see the same facts.

- **Free = obsession hook:** screener, Player Sheet facts, league overview, limited Scratchpad views.
- **Pro = trust for league decisions:** full Scratchpad, valuation assumptions, The Line deep dives and scenarios.
- **Elite = the obsessive tier:** full War Room, richer scenario capacity, proactive intelligence, included model usage when live asks ship.
- **League option (a purchase mode, not a tier):** any league can buy Razzle for the whole league; the weekly Line briefing lands in front of all twelve. One sale = twelve funnel entries.

**Tiers are product objects from Milestone Zero, not Stripe artifacts:** one entitlement registry, seeded dev tiers, a localhost tier switcher. Billing later changes who may hold a tier — never what a tier is. Free must be generous enough that fans fall in love; they pay when their **league** is on the line.

## The staff

| Who | Job | Shows up |
|-----|-----|----------|
| **Razzle** 🐯 | Chief of Staff. Verdict. No hedging. | Everywhere |
| **Dr. Dolphin** 🐬 | Medical. Injuries. Durability. | Everywhere there's player health |
| **Hawkeye** 🎯 | Scout. Usage. Breakouts. Tape. | Usage / breakout surfaces |
| **Bones** 🦴 | Diplomat. Trades. Leverage. | Trade / manager psychology |
| **Octo** 🐙 | Quant. Odds. Projections. EV. | Numbers that end arguments |
| **Atlas** 📚 | Historian. Career arcs. League memory. | History / college-to-pro / manager patterns |

Razzle says **"start him."** Other tools say "consider starting." At Milestone Zero the staff voice is deterministic (templated briefings over real evidence packets); live model voices are an integration layered on later without changing the packets. Orchestration shape in `spec/STAFF.md`.

## The moat (ranked)

1. **League-relative decision quality** — your league, your rules, your picks, your rivals.
2. **Compounding context** — more seasons → richer profiles → harder to leave.
3. **Data density done right** — full NFL weekly history (1999–), the college-to-pro bridge, usage, health, contracts, market values — all keyless, all traceable (`spec/DATA.md`), in service of trust, not feature count.
4. **Community recognition** — r/DynastyFF knows the screenshots; switching mid-season hurts.

The moat is **not** "we use AI." Anyone can rent a model. We're the context layer with a personality.

## Trust pillars (T0–T7) — how work is scored

| ID | Pillar | Pass question | Fail smell |
|----|--------|---------------|------------|
| **T0** | Player accuracy | Is every number traceable to a source row through the crosswalk, with unsupported rules failing closed and visibly? | Wrong player, stale team, silent NA→0 on identity, invented precision |
| **T1** | Decision trust | Would a serious manager act on this for a real decision? | Generic ranking noise |
| **T2** | League-relative | Customized to *this* league's rules, rosters, picks, rivals? | Static trade calc / redraft brain |
| **T3** | Player Sheet | Does the case file get better — land, switch, own, arc, branch? | Dead-end page |
| **T4** | Film-room loop | Helps *what happened → why → what's next* (esp. post-Sunday)? | Feature with no weekly story |
| **T5** | Scratchpad invention | Labeled data becomes a visual, shareable instrument? | JSON dump / unstyled table |
| **T6** | Screenshot gravity | Helpful in a group chat; Razzle colors + watermark recognizable? | Generic SaaS gray |
| **T7** | Free-tier obsession | Free deepens love without giving away paid trust? | Paywall rage / empty free tier |

**Minimum to ship a slice:** T1 + at least one of T3–T5, plus gates in `factory/GATES.md`. **T0 is a floor, not a pillar to trade:** the standard is **zero silent errors** — no invented precision, every number traceable, every unsupported rule visibly marked unavailable (gate G6). One silent wrong stat spends all the trust we sell.

## Instant VETO (do not merge)

- A player number that fails traceback to its source row, or an unsupported league rule silently scored instead of failing closed (T0)
- User-facing copy leads with "AI" (`spec/VOICE.md`)
- Generic advice that ignores league context when context exists
- Silo with zero Player Sheet or cross-room path
- Horizontal sprawl (auth polish, marketing site) advancing no Trust pillar
- Violates `spec/DESIGN.md` (gradients, thin borders, cold fintech vibes)

## Decision framework (in order)

1. Does this increase trust for a real decision? (T1)
2. Is it true for *their* league, not fantasy in general? (T2)
3. Does it strengthen the Player Sheet case file? (T3)
4. Does it help the post-Sunday film-room loop? (T4)
5. Would a dynasty manager screenshot this for the *data*? (T6)
6. Does it match `spec/DESIGN.md`? Sand, chunky, comic energy, warm not cold.
7. Is this the simplest complete version? Ship, then deepen.
8. Does it move toward 1,000 paid users — directly or via a Trust pillar?

If 1–4 are all no and it's not infrastructure, **KILL the slice**.

## Who we're for

**Primary:** dynasty power users on r/DynastyFF — year-round, tool-heavy, allergic to generic ChatGPT takes. **Secondary:** serious redraft players who arrive through screenshots and Line hooks.

Pain we own: *"ChatGPT doesn't know my scoring settings." "Six tabs open for one trade." "I know Dave panics after losses — I can't prove it." "Sunday night and I still don't know why I lost."*

## Distribution — the trade-reply doctrine

**We never promote Razzle.** No launch posts, no ads. Niche trade threads have a massive surplus of people *asking* over competent people *answering*. The play: reply to real trade questions with a small, chill, competent explanation — alongside a Razzle screenshot that shows the reasoning under the asker's league settings. The answer is the marketing; the watermark does the rest.

Flywheel: trade answer → screenshot with reasoning → watermark → free screener → Sleeper connect → Line hook → paid trust.

**Product law that follows:** every shareable surface must work as a *trade answer*. The canonical screenshot is a side-by-side comparison — players and picks, valued under the asker's league settings, assumptions visible. Posting under the Founder's identity is Founder-only.

## Playfulness is not optional

Warm, human, slightly quirky beats enterprise-serious for tools people live in daily. Loading copy: *"pulling film..."* Tiger who's smug because the numbers back it up. Dry wit in the margins; never cringe, never corporate. **If a PR makes Razzle feel like a fintech dashboard, T6 fails even if tests pass.**

## The line

We're testing weekly what's stronger — **our bad luck or the numbers.** Come join us. Bring your league. Razzle already pulled the film.
