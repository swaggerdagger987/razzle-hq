# Gates — Command-First Acceptance

Run from repo root. A slice is DONE only when every applicable gate is green and the outputs are pasted into the commit body. **Evidence lives in commit messages, not in evidence files.**

## G1 — boot

```bash
RAZZLE_DATABASE_URL=sqlite:///$(mktemp -d)/g1.db uv run alembic -c apps/api/alembic.ini upgrade head   # exit 0 on a fresh DB
uv run uvicorn razzle_api.main:app --port 8000 &   # then:
curl -s localhost:8000/health                       # {"status":"ok"}
```

## G2 — tests

```bash
uv run pytest -q    # zero failures (skips allowed)
```

**Stub tests are an automatic FAIL.** A test that asserts nothing, asserts `True`, or never exercises the code under test is treated as a lie about coverage — worse than no test.

## G3 — build

```bash
pnpm --filter web build    # exit 0
```

## G4 — lint

```bash
uv run ruff check && uv run ruff format --check
pnpm --filter web lint
```

## G5 — product (per-slice)

The slice card defines G5: concrete assertions a reviewer can replay. Examples:

- `curl -s 'localhost:8000/api/players?position=RB' | jq length` → ≥ 20
- `/explore` renders ≥20 rows; changing sort updates the URL; refresh preserves state
- screenshot path of the rendered surface (sand background, chunky borders, position colors — `spec/DESIGN.md`)
- voice check when web copy changed: `grep -rEn '\bAI\b|powered by|chatbot|LLM' apps/web/src --include='*.tsx'` → no user-facing hits

When the slice ships a user-facing surface, G5 includes the hallway checklist from `spec/PRODUCT.md` (no dead-end pages) and the screenshot question: **would r/DynastyFF screenshot this for the data?**

## G6 — accuracy (any slice that ingests or displays player data)

```bash
uv run python scripts/verify_data.py --sample 25    # exit 0; zero identity mismatches
```

The harness (built in Stage 0 R-03; until it lands, the same checks run as card-level G5 assertions) verifies per synced source:

- **Random-sample replay** — N random DB rows re-fetched from the source file and compared field-by-field.
- **Identity** — sampled players' gsis_id/name/position/team agree with the crosswalk (`player_ids`); college links replay through the `draft_picks` bridge. Tolerance: **zero**. One wrong player fails the gate and the slice.
- **Coverage honesty** — a league rule outside the compiler's coverage renders the unsupported chip, never a number (spot-checked per connected league).
- **Cross-source reconciliation** — where two sources cover the same fact, values agree within the tolerance stated on the card; mismatches are flagged, never silently overwritten.

## Ship bar

From `spec/NORTH_STAR.md`: a slice ships only with **T1 plus at least one of T3–T5**, none of the instant-VETO conditions, and **T0 green (zero silent errors) wherever player data moved or rendered**. Cite the pillars in the commit body.

## On failure

Fix until green. If genuinely stuck, mark the card BLOCKED with the exact failing command + output and stop — do not commit red, do not weaken a gate to pass it. Gate definitions only change via frontier-model sessions (`factory/ROUTING.md`).
