# Routing — The Command Structure and the Loop

The factory's economics: **expensive judgment, cheap throughput, budgeted always.** This contract is harness-agnostic in principle, but the current mapping is pinned to Cursor cloud agents (2026-07-22, Founder direction). No runner code ships in this repo — any harness that reads `factory/STATE.md`, honors `factory/SLICE.md`, and routes by this file can drive the factory.

## The seats (locked 2026-07-22)

**Model rule: always the maximum reasoning variant a family offers.** When a family adds a higher tier, upgrade the slug here (a dated decisions-log row in `spec/STACK.md`); classes govern, slugs execute.

| Seat | Model (class → current slug) | Billable work | Cadence |
|------|------------------------------|---------------|---------|
| **Founder** | — | Identity-load-bearing calls, stage sign-offs, ignition, credentials, money, public posting | 4 checkpoints + vetoes |
| **CTO** | Fable Max → `claude-fable-5-thinking-xhigh` | Architecture drift, cohesion + taste audits ("is this one product or stitched features"), `spec/` changes, KILL calls, twice-failed leases, escalations | **Periodic** — light through Stages 0–1; first deep pass at the Stage 2 checkpoint; heaviest at Stage 4; plus on-escalation |
| **Captain** (Chief Architect / Release) | GPT Sol Max → `gpt-5.6-sol-xhigh` | **The day-to-day loop.** Majority of design + delegation: details cards into leases, spawns and supervises the fleet, merges lanes, runs gates, sole writer of `factory/STATE.md`, sole toucher of serialized locks, enforces budgets | Continuous — owns the run |
| **Writer** | Grok 4.5 → `cursor-grok-4.5-high` (no max variant exists; highest available) | One lease = one branch = one bounded commit. Adapters, routes, instruments, tests against a frozen contract | Per lease |
| **Auditor** | Grok 4.5 Fast → `cursor-grok-4.5-high-fast` | Read-only fan-outs: golden checks, G6 sampling, reconciliation, screenshot QA, voice greps, adversarial review, test reproduction. Checklists, not mandates | Per wave, in batches |

**Escalation chain:** Writer → Captain (blocked / defective lease) → CTO (spec conflict, architecture, taste, second lease failure) → Founder (identity, credentials, money). A cheap seat that hits a decision not answerable from `spec/` does not guess — it writes the question on the card, marks it BLOCKED, finishes what is safely in scope, and ends clean.

**Model enforcement is mechanical, not aspirational:** the Founder picks the captain's model at launch; the captain pins every subagent's model slug in the spawn call per this table; the LEDGER records seat + model per slice; checkpoint audits verify. One model per seat, never switched mid-session — to use another class mid-task, spawn a subagent pinned to it.

## The lease (the unit of delegation)

Every writer receives a lease containing ALL of — and nothing beyond:

- **Base SHA + lane branch** (`cursor/<lane>-XXXX`) + isolated worktree, own SQLite file (`RAZZLE_DATABASE_URL`), own port pair.
- **File fence** — the exact files it may create/edit. The fence is the worker's whole world: **repo-wide exploration is forbidden**; everything needed (contracts, fixtures, pitfalls, column maps) is pre-digested into the lease. Spelunking is where million-token sheet builds come from.
- **Frozen contracts** — endpoint shapes, module signatures, fixture shapes it builds against.
- **Gates** — G1–G6 as applicable, plus lease-specific G5 assertions.
- **Budget class + turn cap** (below).
- **Handoff format** — one bounded commit, gate evidence in the body, remaining-work note if cut.

## Cost governance (budgets live in the lease, not in vibes)

| Class | Work shape | Token budget (approx) | Turn cap |
|-------|-----------|----------------------|----------|
| **S** | Single component, copy pass, test fix, one audit | ~150k | 15 tool-turns |
| **M** | Standard slice: adapter, instrument, route, viz | ~400k | 40 tool-turns |
| **L** | Kernel work: rules compiler, scenario engine, recovery train | ~900k | 80 tool-turns |

- **Turn caps are the enforceable proxy** for tokens inside the loop; real spend is visible on the Cursor dashboard, and the Founder sets a dashboard spend limit as the hard outer backstop.
- **The 80% rule:** at ~80% of budget a writer must either hand off what is green with a remaining-work note, or file a one-paragraph extension request naming the cause — *defective lease* (scope was wrong: the captain's failure; fix the lease standard upstream) or *genuine scope* (extension granted and logged in the LEDGER row). No silent grinding.
- **Kill-and-reclaim:** the captain kills any seat past its cap or idle. A lease that fails twice escalates to the CTO — never a third writer attempt (rework at the same seat is the write-off).
- **LEDGER accounting:** every row logs seat, model, budget class, and approximate spend. **Pyramid targets, audited at every checkpoint: ≥70% of tokens in Grok seats, ≤20% captain, ≤10% CTO.** Cost-per-shipped-slice must trend flat or down; if it climbs, the lease standard is failing upstream and the loop pauses to fix *that*, not to grind harder.
- Budgets flex when the product genuinely demands it — via the extension protocol, on the record, never by drift.

## The loop (one turn of the run)

1. **Captain reads STATE** — the run-lock, the stage plan, the dependency graph. If a prior run left ACTIVE leases, resume them from their cards; never start parallel copies.
2. **Select ready nodes** whose dependencies are DONE and whose fences are free. Detail them to execution-ready (`factory/SLICE.md`) if they aren't.
3. **Fan out:** create worktrees, spawn writer subagents (models pinned per the seat table) in parallel batches — 4–6 writer leases live at once to start, growing to 10–12 only after two clean merge waves. Auditor fan-outs run in larger batches.
4. **Collect handoffs:** writers push lane branches with gate evidence; auditors return checklist results.
5. **Merge in dependency order** on the integration branch; rerun the full gate suite per batch; bounce failures to an auditor/writer with the exact failing output; append LEDGER rows (with cost); push; update the run PR.
6. **Repeat** until the stage boundary → run the stage's CTO review (Stages 2 and 4 mandatory), write the checkpoint memo (Shipped · Proof · Cost vs pyramid · Asks · Next), and **stop for the Founder**.

**Stops:** stage boundary · a `CLIENT:` blocker (batched, never one interruption at a time) · usage limits (commit what is green, mark cards with exactly what remains — state lives in the repo, never in a session's head; log `limit-cut` on the LEDGER row) · the Founder saying stop.

## The isolation law

**Two live seats never share a file.** Parallelism is manufactured, not hoped for:

- **Migrations are captain-only.** The Alembic chain is serial by nature; every planned table lands in the stage's kernel lease. Writers never author migrations.
- **`main.py`, root layout/providers, package manifests + lockfiles, `tokens.css`, CI workflows, `spec/`, `factory/`** are serialized locks — captain-only, edited between waves, never during fan-out. Routers and routes are pre-registered so writers fill files inside their fence and never touch shared surfaces.
- **`scripts/sync_data.py` discovers adapters via a name → module-path registry with lazy imports** — adding a source touches only the new adapter module; the registry row is a one-line captain-merged edit.
- A lease whose fence overlaps another live lease is a **defective lease** — fix the fence or re-wave; seats never "coordinate."
- **Contract-first integration:** a web writer builds against the pinned contract with a cassette/fixture when its API lane hasn't landed; the captain swaps live at merge.

**Best-of-2 on taste-critical surfaces** (the screener, the workbench, the Line briefing): two writers, same lease, captain picks on T6 and discards the loser. **Review is sampling, never redoing:** deep-check ~1 in 4 fleet slices, screenshot everything user-facing, trust gates for the rest.

## Running it in Cursor (the ignition manual)

1. **One-time:** merge the constitution PR; set a dashboard spend limit.
2. **Ignite:** launch one cloud agent on this repo — **model: GPT Sol Max** — prompt: **"go"**. The captain reads `CLAUDE.md` → `factory/STATE.md` and runs the loop above.
3. **Checkpoint:** the captain ends its turn with the memo; the Founder walks the product (`scripts/dev.sh`), then replies **"continue"** (same agent, full context) or redirects.
4. **Recovery:** if a session dies mid-wave, launch a fresh Sol captain with "go" — run-lock + lease cards resume losslessly.
5. **Optional 24/7:** a scheduled automation that sends "go" on a cadence. **Off by default; Founder-enabled only** (cost-control precedent: the hard-stop banner in the old repo).

Frontier seats have **explicit creative license** inside the rulebook: within `spec/DESIGN.md` and `spec/VOICE.md`, add taste, wit, and craft freely. The line: when a choice is **identity-load-bearing** (a room's purpose, the free/paid line, the valuation philosophy, the mascot's character) and not derivable from `spec/`, surface it to the Founder instead of silently choosing.

## Founder-only

- Posting anywhere public under the Founder's identity (Reddit, social).
- Pricing changes, billing live-mode, deleting data, enabling the 24/7 automation.
- Overriding a VETO condition from `spec/NORTH_STAR.md`.
- Providing credentials: LLM API keys, Stripe, Reddit, DNS. (Milestone Zero requires none.)
