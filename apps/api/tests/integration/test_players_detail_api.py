"""Integration tests for GET /api/players/{gsis_id}.

Seeds Saquon Barkley + Jonathan Taylor with 2 seasons each, 2 weeks of stats per season.
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

SAQUON_ID = "00-0033873"
TAYLOR_ID = "00-0036900"

PLAYER_FIXTURES = [
    {"gsis_id": SAQUON_ID, "name": "Saquon Barkley", "position": "RB", "team": "PHI"},
    {"gsis_id": TAYLOR_ID, "name": "Jonathan Taylor", "position": "RB", "team": "IND"},
]

WEEK_STAT_2024 = [
    {"player_id": SAQUON_ID, "week": 1, "rush_att": 20.0, "rush_yd": 109.0, "rush_td": 1.0},
    {"player_id": SAQUON_ID, "week": 2, "rush_att": 18.0, "rush_yd": 90.0},
    {"player_id": TAYLOR_ID, "week": 1, "rush_att": 15.0, "rush_yd": 72.0, "rush_td": 1.0},
    {"player_id": TAYLOR_ID, "week": 2, "rush_att": 12.0, "rush_yd": 55.0},
]

WEEK_STAT_2025 = [
    {"player_id": SAQUON_ID, "week": 1, "rush_att": 22.0, "rush_yd": 120.0, "rush_td": 2.0},
    {"player_id": SAQUON_ID, "week": 2, "rush_att": 19.0, "rush_yd": 85.0},
    {"player_id": TAYLOR_ID, "week": 1, "rush_att": 14.0, "rush_yd": 60.0},
    {"player_id": TAYLOR_ID, "week": 2, "rush_att": 16.0, "rush_yd": 78.0, "rush_td": 1.0},
]


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'player_detail_test.db'}"
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
        upsert_players(session, PLAYER_FIXTURES)
        upsert_week_stats(session, 2024, WEEK_STAT_2024)
        upsert_week_stats(session, 2025, WEEK_STAT_2025)
        session.commit()


def _make_override(session_factory):
    def override():
        with session_factory() as session:
            yield session

    return override


async def test_player_detail_returns_seasons_and_weeks(session_factory) -> None:
    """GET /api/players/{saquon_id} must return 2 seasons each with 2 week_stat rows."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/players/{SAQUON_ID}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["gsis_id"] == SAQUON_ID
    assert data["name"] == "Saquon Barkley"
    assert data["position"] == "RB"
    assert len(data["seasons"]) == 2
    # Seasons returned newest-first (2025, 2024).
    assert data["seasons"][0]["season"] == 2025
    assert len(data["seasons"][0]["week_stats"]) == 2
    assert data["seasons"][1]["season"] == 2024
    assert len(data["seasons"][1]["week_stats"]) == 2


async def test_player_detail_week_stats_values(session_factory) -> None:
    """Week stats in the response must match the seeded values."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/players/{SAQUON_ID}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    # Find 2025 season.
    seasons_by_year = {s["season"]: s for s in resp.json()["seasons"]}
    weeks_2025 = {w["week"]: w for w in seasons_by_year[2025]["week_stats"]}
    assert weeks_2025[1]["rush_yd"] == 120.0
    assert weeks_2025[1]["rush_td"] == 2.0
    assert weeks_2025[2]["rush_yd"] == 85.0


async def test_player_detail_not_found_returns_404(session_factory) -> None:
    """An unknown gsis_id must return 404, not 500."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/players/00-9999999")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 404


async def test_player_detail_no_stats_returns_empty_seasons(session_factory) -> None:
    """A known player with no week stats should return seasons=[]."""
    with session_factory() as session:
        upsert_players(session, PLAYER_FIXTURES)
        session.commit()

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/players/{SAQUON_ID}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["gsis_id"] == SAQUON_ID
    assert data["seasons"] == []


async def test_adjacent_players_endpoint(session_factory) -> None:
    """GET /api/players/{gsis_id}/adjacent returns neighbours in alphabetical order."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Jonathan Taylor (J) comes before Saquon Barkley (S) alphabetically.
            resp = await client.get(
                f"/api/players/{SAQUON_ID}/adjacent",
                params={"season": 2025},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    adj = resp.json()
    # Saquon (S) comes after Jonathan (J), so prev = Taylor, next = None.
    assert adj["prev_gsis_id"] == TAYLOR_ID
    assert adj["next_gsis_id"] is None
