from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session, sessionmaker

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

WEEK_STAT_FIXTURES = [
    {"player_id": "00-0000001", "week": 1, "rush_att": 18.0, "rush_yd": 95.0, "rush_td": 1.0},
    {"player_id": "00-0000002", "week": 1, "rush_att": 12.0, "rush_yd": 51.0},
]


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'razzle.db'}"
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


def _counts(session: Session) -> tuple[int, int]:
    players = session.execute(sa.text("SELECT COUNT(*) FROM players")).scalar_one()
    stats = session.execute(sa.text("SELECT COUNT(*) FROM player_week_stats")).scalar_one()
    return players, stats


def test_upserts_are_idempotent(session_factory) -> None:
    with session_factory() as session:
        upsert_players(session, PLAYER_FIXTURES)
        upsert_week_stats(session, 2024, WEEK_STAT_FIXTURES)
        session.commit()
        first_counts = _counts(session)

        upsert_players(session, PLAYER_FIXTURES)
        upsert_week_stats(session, 2024, WEEK_STAT_FIXTURES)
        session.commit()

        assert _counts(session) == first_counts == (3, 2)
        rush_yd = session.execute(
            sa.text(
                "SELECT rush_yd FROM player_week_stats"
                " WHERE player_id = '00-0000001' AND season = 2024 AND week = 1"
            )
        ).scalar_one()
        assert rush_yd == 95.0


async def test_get_players_filters_by_position(session_factory) -> None:
    with session_factory() as session:
        upsert_players(session, PLAYER_FIXTURES)
        session.commit()

    def override_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/players", params={"position": "RB", "limit": 100})
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    players = response.json()["players"]
    assert [player["gsis_id"] for player in players] == ["00-0000001", "00-0000002"]
    assert {player["position"] for player in players} == {"RB"}
