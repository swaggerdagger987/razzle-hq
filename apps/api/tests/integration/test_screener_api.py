"""Integration tests for the screener API endpoint.

Reuses the session_factory pattern from test_players_api.py.
Seeds 2 RBs + 1 QB with 2 weeks each of 2024 stats.
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

PLAYER_FIXTURES = [
    {"gsis_id": "00-0000001", "name": "Alpha Back", "position": "RB", "team": "SF"},
    {"gsis_id": "00-0000002", "name": "Bravo Back", "position": "RB", "team": "DET"},
    {"gsis_id": "00-0000003", "name": "Charlie Passer", "position": "QB", "team": "BUF"},
]

# 2 RBs with 2 weeks each, 1 QB with 2 weeks
WEEK_STAT_FIXTURES = [
    # Alpha Back: week 1 + week 2 (total rush_yd = 95 + 60 = 155)
    {
        "player_id": "00-0000001",
        "week": 1,
        "rush_att": 18.0,
        "rush_yd": 95.0,
        "rush_td": 1.0,
    },
    {
        "player_id": "00-0000001",
        "week": 2,
        "rush_att": 14.0,
        "rush_yd": 60.0,
        "rush_td": 0.0,
    },
    # Bravo Back: week 1 + week 2 (total rush_yd = 51 + 42 = 93)
    {
        "player_id": "00-0000002",
        "week": 1,
        "rush_att": 12.0,
        "rush_yd": 51.0,
    },
    {
        "player_id": "00-0000002",
        "week": 2,
        "rush_att": 10.0,
        "rush_yd": 42.0,
    },
    # Charlie Passer: week 1 + week 2
    {
        "player_id": "00-0000003",
        "week": 1,
        "pass_att": 32.0,
        "pass_yd": 240.0,
        "pass_td": 2.0,
    },
    {
        "player_id": "00-0000003",
        "week": 2,
        "pass_att": 28.0,
        "pass_yd": 195.0,
        "pass_td": 1.0,
    },
]


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'screener_test.db'}"
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
        upsert_week_stats(session, 2024, WEEK_STAT_FIXTURES)
        session.commit()


def _make_override(session_factory):
    def override():
        with session_factory() as session:
            yield session

    return override


async def test_season_totals_are_summed_and_games_counted(session_factory) -> None:
    """Alpha Back's rush_yd should be wk1+wk2 and games should be 2."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "position": "RB", "sort": "name", "dir": "asc"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    rows = {r["gsis_id"]: r for r in data["rows"]}
    alpha = rows["00-0000001"]
    assert alpha["games"] == 2
    assert alpha["rush_yd"] == 155.0
    assert alpha["rush_att"] == 32.0


async def test_sort_rush_yd_desc_orders_correctly(session_factory) -> None:
    """Alpha Back (155 rush_yd) should come before Bravo Back (93 rush_yd) when sorted desc."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "position": "RB", "sort": "rush_yd", "dir": "desc"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 2
    assert rows[0]["name"] == "Alpha Back"
    assert rows[1]["name"] == "Bravo Back"
    assert rows[0]["rush_yd"] >= rows[1]["rush_yd"]


async def test_position_filter_returns_only_matching(session_factory) -> None:
    """position=RB must return only RBs; total must match."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "position": "RB"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(r["position"] == "RB" for r in data["rows"])


async def test_invalid_sort_returns_422(session_factory) -> None:
    """An unknown sort key must return 422, not 500."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "sort": "evil_column"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422


async def test_invalid_position_returns_422(session_factory) -> None:
    """position=K is not in the allowed literal and must return 422."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "position": "K"},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422


async def test_season_with_no_rows_returns_empty(session_factory) -> None:
    """Querying a season with no stats returns empty rows and total=0, not a 500."""
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2020},  # valid year but no data seeded
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["rows"] == []
