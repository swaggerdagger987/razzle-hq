"""Integration tests for GET /api/players/{gsis_id}.

Uses synthetic player identities — not nflverse goldens.
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

ALPHA_ID = "pd-0000001"
BRAVO_ID = "pd-0000002"

PLAYER_FIXTURES = [
    {"gsis_id": ALPHA_ID, "name": "Alpha Detail", "position": "RB", "team": "PHI"},
    {"gsis_id": BRAVO_ID, "name": "Bravo Detail", "position": "RB", "team": "IND"},
]

WEEK_STAT_2024 = [
    {"player_id": ALPHA_ID, "week": 1, "rush_att": 20.0, "rush_yd": 109.0, "rush_td": 1.0},
    {"player_id": ALPHA_ID, "week": 2, "rush_att": 18.0, "rush_yd": 90.0},
    {"player_id": BRAVO_ID, "week": 1, "rush_att": 15.0, "rush_yd": 72.0, "rush_td": 1.0},
    {"player_id": BRAVO_ID, "week": 2, "rush_att": 12.0, "rush_yd": 55.0},
]

WEEK_STAT_2025 = [
    {"player_id": ALPHA_ID, "week": 1, "rush_att": 22.0, "rush_yd": 120.0, "rush_td": 2.0},
    {"player_id": ALPHA_ID, "week": 2, "rush_att": 19.0, "rush_yd": 85.0},
    {"player_id": BRAVO_ID, "week": 1, "rush_att": 14.0, "rush_yd": 60.0},
    {"player_id": BRAVO_ID, "week": 2, "rush_att": 16.0, "rush_yd": 78.0, "rush_td": 1.0},
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
    """GET /api/players/{id} must return 2 seasons each with 2 week_stat rows."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/players/{ALPHA_ID}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["gsis_id"] == ALPHA_ID
    assert data["name"] == "Alpha Detail"
    assert data["position"] == "RB"
    assert len(data["seasons"]) == 2
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
            resp = await client.get(f"/api/players/{ALPHA_ID}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
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
            resp = await client.get(f"/api/players/{ALPHA_ID}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["gsis_id"] == ALPHA_ID
    assert data["seasons"] == []


async def test_adjacent_players_endpoint(session_factory) -> None:
    """GET /api/players/{gsis_id}/adjacent returns neighbours in alphabetical order."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Bravo Detail (B) comes before Alpha Detail (A)? No — Alpha < Bravo.
            # Alpha Detail first, Bravo Detail second.
            resp = await client.get(
                f"/api/players/{BRAVO_ID}/adjacent",
                params={"season": 2025},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    adj = resp.json()
    # Bravo is second alphabetically; prev = Alpha, next = None.
    assert adj["prev_gsis_id"] == ALPHA_ID
    assert adj["next_gsis_id"] is None
