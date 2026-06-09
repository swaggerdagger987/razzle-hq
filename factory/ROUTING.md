# Model Routing — Expensive Judgment, Cheap Throughput

The factory's economics: **frontier models decide, cheap models build.** This contract is harness-agnostic — Claude Code sessions, CI-triggered runs, or any future loop runner must honor it. No runner code ships in this repo.

## The staffing ladder

Run the factory like a services firm: the expensive seat signs the work, the cheap seats produce it, and profitability is the leverage ratio between them. Class names, not pinned versions — always use the current best model in each class.

| Seat | Model class | Billable work |
|---|---|---|
| **Partner on the file** | Most capable available (top tier above Opus) | Signs opinions: `spec/` changes, NORTH_STAR-level direction, KILL calls, pricing/identity questions, T6 taste verdicts, architecture that is expensive to reverse. Short, rare engagements. |
| **Senior manager** | Opus-class | Runs the file: frontier planning passes (sketch → execution-ready build sheet), answering BLOCKED cards, reviewing shipped user-facing surfaces, BACKLOG ordering, splitting oversized cards. |
| **Senior associate** | Sonnet-class | **The workhorse.** Executes an ACTIVE slice whose card has a complete scope fence and concrete G5 assertions — code, tests, gates, commit. Mechanical ports, adapters against `spec/DATA.md`, test writing against a stated contract. |
| **Analyst** | Haiku-class | Fully-specified mechanical work: gate-failure fix loops where the failure is local (failing test, lint, type error), running gate suites, data spot-checks, fan-out searches. Best used as subagents inside a larger session. |

Partner/senior-manager seats may always work *down* the ladder when no cheaper session is available — but a card detailed to the execution-ready standard exists precisely so they don't have to.

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

**Run lock:** if a run starts and STATE.md already shows an ACTIVE slice, the prior run was interrupted — resume that card from its logged state; never start a parallel copy.



Frontier sessions have **explicit creative license** inside the rulebook: within `spec/DESIGN.md` and `spec/VOICE.md`, add taste, wit, and craft freely — margin notes, loading copy, the extra 10% that makes a surface screenshot-worthy. Don't ask permission to be excellent. The line: when a choice is **identity-load-bearing** (changes what Razzle *is* — a room's purpose, the free/paid line, the valuation philosophy, the mascot's character) and not derivable from `spec/`, surface it to the Founder instead of silently choosing. Liberties within the lines: take them. Liberties *with* the lines: discuss first.

## The escalation rule

A cheap-model session that hits a decision **not answerable from `spec/`** does not guess. It writes the question on the slice card, marks it BLOCKED, finishes what is safely in scope, and ends clean — a review note up the ladder. A higher seat (or the Founder) answers on the card, flips it back to OPEN, and the next cheap session proceeds.

Signals you must escalate: the fix wants a new dependency · two specs appear to conflict · the slice needs a product call the card didn't make · the gate itself seems wrong.

## Budget (hard constraints)

- **Primary engine: the Founder's Claude subscription.** All routine factory work runs inside subscription-covered Claude Code sessions. Plan heavy slices for when the usage window is fresh (limits reset on ~5-hour windows); do frontier planning/review early in a window, then let cheap throughput burn the remainder.
- **API credits: $150 total, overflow only.** Spend them solely to *finish* something a session ran out of limits mid-way through — never to start work a future session could do. Log any API spend as a line in the STATE.md ledger row for that slice.
- A session that hits usage limits mid-slice commits what is green, marks the card with exactly what remains, and ends clean — the next session resumes from the card. Never leave the resume state in your head. **Also log it:** append `limit-cut` to that slice's LEDGER row note.
- **Plan-upgrade trigger (Pro → Max):** the upgrade decision is evidence-based, not vibes. Stay on the current plan while it isn't the binding constraint. Upgrade when the LEDGER shows **2+ `limit-cut` sessions in a week** while launch-path slices remain — at that point window capacity, not judgment or card quality, is what's throttling the July 28 date. Until then, the proof of the system is throughput: slices shipped fully gated, zero reopened.

## Founder-only

- Posting anywhere public under the Founder's identity (Reddit, social).
- Pricing changes, billing live-mode, deleting data.
- Overriding a VETO condition from `spec/NORTH_STAR.md`.
- Providing credentials: LLM API keys, Stripe, Reddit. Everything else the factory handles itself; the Founder's standing role is veto power when direction gets weird.

## Cadence (suggested, not enforced by tooling)

One frontier planning pass keeps BACKLOG ordered and answers BLOCKED cards; cheap sessions burn down the top of BACKLOG one slice at a time; a frontier review pass audits shipped surfaces against T1–T7 every few slices. State lives in `factory/STATE.md` — any harness that reads it, honors the slice contract, and routes by this file can drive the factory.
