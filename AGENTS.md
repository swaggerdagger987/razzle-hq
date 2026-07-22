# AGENTS.md

Razzle HQ. Read `CLAUDE.md` first — it holds the run commands, hard rules, and session protocol. This file only adds Cursor Cloud environment notes.

## Cursor Cloud specific instructions

The update script (`uv sync --all-packages` + `pnpm install`) keeps dependencies fresh on startup. It does not install `uv` or run migrations — those are handled below.

- **`uv` is on `~/.local/bin`**, added to `PATH` via `~/.bashrc`. If `uv: command not found`, run `export PATH="$HOME/.local/bin:$PATH"`.
- **Tooling already matches CI:** Node 22, pnpm 10.33 (preinstalled), Python 3.12. No version managers needed; nvm is not required.
- **Database is embedded SQLite** at `data/razzle.db` (gitignored, not a separate service). The update script does NOT migrate. Before running/testing the API, apply migrations: `uv run alembic -c apps/api/alembic.ini upgrade head`. `scripts/dev.sh` runs this for you on startup.
- **Env file:** copy `.env.example` to `.env` at the repo root if missing (defaults work out of the box: API `:8000`, web `:3000`).
- **Run both services:** `scripts/dev.sh` starts the API (`:8000`) and web (`:3000`). To run them separately: `uv run uvicorn razzle_api.main:app --reload --port 8000` and `pnpm --filter web dev`. The web app reads the API base from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); the API hard-codes CORS for `localhost:3000`.
- **Data is empty by default.** The `/scoring` page works without data (it posts sample players to the engine). To populate `players`/`player_week_stats`, run `uv run python scripts/sync_data.py --quick` — this needs internet (nflverse CSVs from github.com) and is optional.
- **pnpm build-script warning** for `sharp`/`unrs-resolver` is benign; `pnpm --filter web build` and `dev` succeed without approving them.
- **Checks (mirror CI in `.github/workflows/ci.yml`):** `uv run ruff check`, `uv run ruff format --check`, `uv run pytest -q`, `pnpm --filter web lint`, `pnpm --filter web build`.
