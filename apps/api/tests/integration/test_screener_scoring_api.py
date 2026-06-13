"""Integration tests for screener API custom-scoring (S-004).

Seeds 1 RB with known week stats and verifies fantasy_points are computed
correctly for each scoring preset and via custom scoring_rules overrides.

Expected values (standard scoring defaults from ScoringRules):
  rush_yd: 0.1 pts/yd  →  100 yd * 0.1 = 10.0
  rush_td: 6.0          →  1 td  * 6.0 = 6.0
  rec:     0.0 (standard), 1.0 (PPR), 0.5 (half)
  => standard: 10 + 6 = 16.0
  => PPR (0 receptions): 10 + 6 = 16.0
  => half (0 receptions): 10 + 6 = 16.0
"""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from razzle_api.config import get_settings
from razzle_api.core.db import get_session
from razzle_api.ingest.nflverse import upsert_players, upsert_week_stats
from razzle_api.main import app

API_DIR = Path(__file__).resolve().parents[2]

# --- fixtures ---

_PLAYERS = [
    {"gsis_id": "sc-001", "name": "Rush Rusher", "position": "RB", "team": "KC"},
    {"gsis_id": "sc-002", "name": "Catch Catcher", "position": "RB", "team": "SF"},
    {"gsis_id": "sc-003", "name": "Arm Slinger", "position": "QB", "team": "BUF"},
]

_WEEK_STATS = [
    # Rush Rusher: 100 rush_yd + 1 rush_td, no receiving
    {"player_id": "sc-001", "week": 1, "rush_yd": 100.0, "rush_td": 1.0},
    # Catch Catcher: 50 rush_yd + 5 rec + 60 rec_yd
    {"player_id": "sc-002", "week": 1, "rush_yd": 50.0, "rec": 5.0, "rec_yd": 60.0},
    # Arm Slinger: 300 pass_yd + 3 pass_td
    {"player_id": "sc-003", "week": 1, "pass_yd": 300.0, "pass_td": 3.0},
]


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'scoring_test.db'}"
    monkeypatch.setenv("RAZZLE_DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(API_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_DIR / "migrations"))
        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        yield sessionmaker(engine, expire_on_commit=False)
        engine.dispose()
    finally:
        get_settings.cache_clear()


def _seed(session_factory) -> None:
    with session_factory() as session:
        upsert_players(session, _PLAYERS)
        upsert_week_stats(session, 2024, _WEEK_STATS)
        session.commit()


def _make_override(session_factory):
    def override():
        with session_factory() as session:
            yield session

    return override


# --- tests ---


async def test_standard_fantasy_points_correct(session_factory) -> None:
    """Rush Rusher: 100 rush_yd * 0.1 + 1 rush_td * 6 = 16.0 (standard)."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "position": "RB",
                    "scoring_preset": "standard",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows["sc-001"]["fantasy_points"] == 16.0


async def test_ppr_adds_reception_points(session_factory) -> None:
    """Catch Catcher: 50*0.1 + 5 rec*1.0 + 60*0.1 = 5 + 5 + 6 = 16.0 PPR."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "position": "RB",
                    "scoring_preset": "PPR",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    # 50 rush_yd=5 + 5 rec*1=5 + 60 rec_yd=6 = 16.0
    assert rows["sc-002"]["fantasy_points"] == 16.0
    # standard has rec=0: 50*0.1 + 60*0.1 = 11.0 — PPR must be higher
    # Rush Rusher stays 16 with PPR (no recs)
    assert rows["sc-001"]["fantasy_points"] == 16.0


async def test_half_ppr_scoring(session_factory) -> None:
    """Catch Catcher half-PPR: 50*0.1 + 5 rec*0.5 + 60*0.1 = 5 + 2.5 + 6 = 13.5."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "position": "RB",
                    "scoring_preset": "half",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows["sc-002"]["fantasy_points"] == 13.5


async def test_custom_scoring_rules_override(session_factory) -> None:
    """Custom pass_td=6 override: Arm Slinger 300*0.04 + 3*6 = 12 + 18 = 30.0."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        import json

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "position": "QB",
                    "scoring_preset": "standard",
                    "scoring_rules": json.dumps({"pass_td": 6}),
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    # Default pass_td is 4.0; override to 6.0 → 300*0.04 + 3*6 = 12 + 18 = 30.0
    assert rows["sc-003"]["fantasy_points"] == 30.0


async def test_fantasy_points_sort_desc(session_factory) -> None:
    """Sort by fantasy_points desc: Rush Rusher (16) before Catch Catcher (11 standard)."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "position": "RB",
                    "sort": "fantasy_points",
                    "dir": "desc",
                    "scoring_preset": "standard",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = resp.json()["rows"]
    # Rush Rusher: 16.0, Catch Catcher (standard, rec=0): 5 + 6 = 11.0
    assert len(rows) == 2
    assert rows[0]["gsis_id"] == "sc-001"
    fp_values = [r["fantasy_points"] for r in rows]
    assert fp_values[0] >= fp_values[1]


async def test_fantasy_points_field_present(session_factory) -> None:
    """All screener rows must include a fantasy_points float field."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    for row in resp.json()["rows"]:
        assert "fantasy_points" in row
        assert isinstance(row["fantasy_points"], (int, float))


async def test_invalid_scoring_rules_json_returns_422(session_factory) -> None:
    """Malformed scoring_rules JSON must return 422."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "scoring_rules": "not-json"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422
