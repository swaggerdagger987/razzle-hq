# Model Routing — Expensive Judgment, Cheap Throughput

The factory's economics: **frontier models decide, cheap models build.** This contract is harness-agnostic — Claude Code sessions, CI-triggered runs, or any future loop runner must honor it. No runner code ships in this repo.

## The staffing ladder

Run the factory like a services firm: the expensive seat signs the work, the cheap seats produce it, and profitability is the leverage ratio between them. Class names, not pinned versions — always use the current best model in each class. **Current mapping (2026-07-22, Founder direction): architect/partner seats run Fable-class thinking models; fleet seats run Grok 4.5-class (fast variant for analysts).**

| Seat | Model class | Billable work |
|---|---|---|
| **Partner on the file / Architect** | Fable-class (most capable available) | Signs opinions: `spec/` changes, NORTH_STAR-level direction, KILL calls, pricing/identity questions, T6 taste verdicts, architecture that is expensive to reverse. In swarm runs: owns the wave plan, authors Wave 0, merges, reviews. |
| **Senior manager** | Fable-class thinking | Runs the file: frontier planning passes (sketch → execution-ready build sheet), answering BLOCKED cards, reviewing shipped user-facing surfaces, BACKLOG ordering, splitting oversized cards. In swarm runs this folds into the architect seat. |
| **Fleet associate** | Grok 4.5-class | **The workhorse.** Executes an ACTIVE slice whose card has a complete scope fence and concrete G5 assertions — code, tests, gates, commit. One agent = one card = one branch. Mechanical ports, adapters against `spec/DATA.md`, panels against the chart kit, test writing against a stated contract. |
| **Fleet analyst** | Grok 4.5-fast / Composer-class | Fully-specified mechanical work: gate-failure fix loops where the failure is local (failing test, lint, type error), running gate suites, accuracy sampling (G6), screenshot QA fan-outs, voice greps. |

Partner/architect seats may always work *down* the ladder when no cheaper seat is available — but a card detailed to the execution-ready standard exists precisely so they don't have to.

## Engagement economics

- **The execution-ready card is the leverage instrument.** It is the partner-reviewed workpaper that lets a Sonnet-class session finish a slice with zero judgment calls. Money spent detailing a card at the top of the ladder is recovered many times over at the bottom. A defective card (associate had to guess) is a routing failure — fix the card standard, not just the slice.
- **Pyramid target:** the bulk of tokens land at Sonnet-class or below; partner-seat share stays small. A partner doing associate work is the firm losing money even when the output is good.
- **Review is sampling, never redoing.** Higher seats audit gate evidence in commit bodies and spot-check the surface; they do not re-implement. The gates exist so a 10-minute review is sufficient.
- **Rework is the write-off.** A reopened slice costs triple (build + diagnose + rebuild, usually at a higher seat). Never weaken a gate to make a session "profitable" — that converts margin into write-offs later.
- **One model per session.** Switching models mid-session discards the prompt cache. To use a cheaper seat mid-session, spawn a subagent pinned to that model instead.

## Engagement runs (the client says "start")

The Founder is the client; the factory is the firm. When the Founder says **start** (or "go"), the session becomes the **engagement lead** and runs without further instruction:

1. Claim the topmost execution-ready card. Delegate its implementation to a **fresh associate subagent** (Sonnet-class), whose entire brief is CLAUDE.md + the card — the workpaper standard means it needs nothing else. Analyst subagents (Haiku-class) handle local gate-failure fix loops.
2. The lead reviews the associate's gate evidence (sampling, not redoing), commits per the session protocol, pushes, and confirms CI green.
3. Repeat with the next card. If no card is execution-ready, the lead does a frontier pass to detail the top sketches, then continues.
4. The run ends only on: usage limits (log `limit-cut`, leave a clean resume state), all remaining work blocked on client deliverables, or the Founder saying stop.

**Client deliverables** (things only the Founder can provide — credentials, DNS, approvals on identity-load-bearing calls): log each as a `CLIENT:` line under Blockers in `factory/STATE.md`, route around it to the next workable card, and **batch requests** — present the full list at the end of the run, not one interruption at a time. A run that ends because the client owes materials is a healthy run; a run that stalls without logging what it needs is a failed one.

**The client memo:** every engagement run ends with a status memo to the Founder, written like an email a client actually wants to read. Fixed shape: **Shipped** (slices DONE, one line each) · **Proof** (gates green, CI run links, screenshots of any user-facing surface attached) · **Usage** (slices this run, whether the run was limit-cut) · **Asks** (the batched `CLIENT:` list, or "nothing needed") · **Next** (the card the next run will claim). No memo, no finished run. The STATE.md LEDGER is the cumulative record behind the memos.

**Run lock:** if a run starts and STATE.md already shows an ACTIVE slice, the prior run was interrupted — resume that card from its logged state; never start a parallel copy. (In swarm runs the lock is per-card: many cards are legally ACTIVE at once, each owned by exactly one seat, listed in the STATE.md wave table.)

## Swarm runs (the client says "swarm") — dozens to 100 seats

Engagement runs are serial: one slice at a time. A **swarm run** trades serialism for a wave plan: one architect seat plus a fleet of associate seats executing many fenced slices in parallel. Same slice contract, same gates — the only new physics is **isolation**.

**Seats.** One **Architect** (Fable-class): owns the wave plan, authors Wave 0, details cards at wave start, merges, reviews; never implements fleet slices while the fleet is live. **Fleet associates** (Grok 4.5-class): one agent = one card = one branch; the entire brief is CLAUDE.md + the card. **Fleet analysts** (Grok 4.5-fast/Composer-class): gate-fix loops, G6 accuracy sampling, screenshot QA, voice greps. Taste-critical surfaces (the screener, the workbench, the Bureau Briefing) may run **best-of-2 seats** on the same card; the architect picks the winner on T6 and discards the other branch.

**The isolation law: two live seats never share a file.** Parallelism is *created* in Wave 0, not hoped for:

- **Migrations are architect-only.** The Alembic chain is serial by nature; every planned table lands in Wave 0. Fleet agents never author migrations.
- **`main.py` reaches final form in Wave 0:** every planned router pre-registered (empty routers are legal). Fleet agents fill router/service files inside their fence and never touch `main.py`.
- **The web shell reaches final form in Wave 0:** nav with all planned routes, providers, panel registry with all Launch-10 entries, entitlement registry, chart kit, tier switcher. Fleet agents fill pages and feature dirs inside their fence.
- **`scripts/sync_data.py` discovers adapters via a name → module-path registry with lazy imports** — adding a source touches only the new adapter module (the registry line is a one-line architect-merged row).
- A card whose fence overlaps another live card is a **defective card** — fix the fence or re-wave it; seats never "coordinate."

**Contract-first integration.** Cards pin interfaces (endpoint shapes, module signatures, fixture shapes). A web seat builds against the pinned contract with a fixture when its API seat hasn't landed; the architect's wave merge swaps fixture for live and runs the full gate suite once per merge batch.

**Wave protocol.**

1. Architect lands Wave 0 on the integration branch; full gates green; details the wave's cards to execution-ready.
2. Fan-out: each fleet seat gets CLAUDE.md + its card, implements on its own branch, runs G1–G6 scoped to its slice, pushes.
3. Architect merges in card order, resolves seam-only conflicts (registry rows), reruns gates per batch, bounces failures to an analyst with the exact failing output.
4. Between waves: sampling review (gate evidence + a screenshot of every user-facing surface), STATE.md wave table updated, next wave detailed.
5. The run ends per engagement-run rules: client memo, batched `CLIENT:` asks, clean tree.

**Review is sampling at fleet scale too:** deep-check ~1 in 4 fleet slices, screenshot everything user-facing, trust gates for the rest. Any fleet slice reopened twice is taken over by the architect and logged as a write-off.



Frontier sessions have **explicit creative license** inside the rulebook: within `spec/DESIGN.md` and `spec/VOICE.md`, add taste, wit, and craft freely — margin notes, loading copy, the extra 10% that makes a surface screenshot-worthy. Don't ask permission to be excellent. The line: when a choice is **identity-load-bearing** (changes what Razzle *is* — a room's purpose, the free/paid line, the valuation philosophy, the mascot's character) and not derivable from `spec/`, surface it to the Founder instead of silently choosing. Liberties within the lines: take them. Liberties *with* the lines: discuss first.

## The escalation rule

A cheap-model session that hits a decision **not answerable from `spec/`** does not guess. It writes the question on the slice card, marks it BLOCKED, finishes what is safely in scope, and ends clean — a review note up the ladder. A higher seat (or the Founder) answers on the card, flips it back to OPEN, and the next cheap session proceeds.

Signals you must escalate: the fix wants a new dependency · two specs appear to conflict · the slice needs a product call the card didn't make · the gate itself seems wrong.

## Engines (2026-07-22 refit — supersedes the Claude-subscription budget)

- **Runs execute on Cursor cloud agents.** Architect seats: Fable-class thinking models. Fleet seats: Grok 4.5-class (fast variant for analysts). One model per seat; a seat never switches models mid-session — to use a different class mid-task, spawn a subagent pinned to it.
- **Pyramid discipline unchanged:** the bulk of tokens land in fleet seats; the architect's share stays small. An architect implementing fleet slices while the fleet is live is the firm losing money even when the output is good.
- A seat that dies mid-slice leaves its card marked with exactly what remains (branch name, failing gate, next command) — any seat resumes it cheaply. State lives on cards, never in a session's head. Log interruptions as `limit-cut` on the LEDGER row.

## Founder-only

- Posting anywhere public under the Founder's identity (Reddit, social).
- Pricing changes, billing live-mode, deleting data.
- Overriding a VETO condition from `spec/NORTH_STAR.md`.
- Providing credentials: LLM API keys, Stripe, Reddit. Everything else the factory handles itself; the Founder's standing role is veto power when direction gets weird.

## Cadence (suggested, not enforced by tooling)

One frontier planning pass keeps BACKLOG ordered and answers BLOCKED cards; fleet seats burn down the top of BACKLOG (serially in engagement runs, wave-parallel in swarm runs); a frontier review pass audits shipped surfaces against T0–T7 every few slices. State lives in `factory/STATE.md` — any harness that reads it, honors the slice contract, and routes by this file can drive the factory.
