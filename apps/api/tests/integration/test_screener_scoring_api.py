"""Integration tests for screener custom-scoring and golden replay (S-004 recovery)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from razzle_api.config import get_settings
from razzle_api.core.db import get_session
from razzle_api.domain.scoring import presets as scoring_presets
from razzle_api.domain.scoring.engine import PlayerWeekStats, score_week
from razzle_api.ingest.nflverse import STAT_COLUMNS, map_week_row, upsert_players, upsert_week_stats
from razzle_api.main import app
from razzle_api.services import screener_service

API_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
GOLDEN_PATH = FIXTURES_DIR / "nflverse_2025_screener_goldens.json"

_PLAYERS = [
    {"gsis_id": "sc-001", "name": "Rush Rusher", "position": "RB", "team": "KC"},
    {"gsis_id": "sc-002", "name": "Catch Catcher", "position": "RB", "team": "SF"},
    {"gsis_id": "sc-003", "name": "Arm Slinger", "position": "QB", "team": "BUF"},
]

_WEEK_STATS = [
    {"player_id": "sc-001", "week": 1, "rush_yd": 100.0, "rush_td": 1.0},
    {"player_id": "sc-002", "week": 1, "rush_yd": 50.0, "rec": 5.0, "rec_yd": 60.0},
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
    assert rows["sc-002"]["fantasy_points"] == 16.0
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


@pytest.mark.parametrize(
    "rules",
    [
        {"unknown_key": 1},
        {"pass_td": "six"},
        {"pass_td": {"nested": 6}},
        {"passing": {"pass_td": 6}},
    ],
)
async def test_unknown_nonnumeric_nested_rules_return_422(session_factory, rules) -> None:
    _seed(session_factory)
    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={"season": 2024, "scoring_rules": json.dumps(rules)},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422


async def test_fantasy_sort_cap_returns_422(session_factory, monkeypatch) -> None:
    """Over-cap fantasy_points sort must 422 without seeding thousands of rows."""
    _seed(session_factory)
    monkeypatch.setattr(screener_service, "MAX_FANTASY_POINT_SORT_PLAYERS", 1)
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
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 422


async def test_limit_offset_preserve_total(session_factory) -> None:
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
                    "limit": 1,
                    "offset": 0,
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["rows"]) == 1


async def test_descending_fantasy_ties_use_gsis_id_asc(session_factory) -> None:
    """Equal fantasy points always break ties by gsis_id ASC, even when dir=desc."""
    players = [
        {"gsis_id": "tie-b", "name": "Tie B", "position": "RB", "team": "KC"},
        {"gsis_id": "tie-a", "name": "Tie A", "position": "RB", "team": "SF"},
    ]
    weeks = [
        {"player_id": "tie-b", "week": 1, "rush_yd": 100.0},
        {"player_id": "tie-a", "week": 1, "rush_yd": 100.0},
    ]
    with session_factory() as session:
        upsert_players(session, players)
        upsert_week_stats(session, 2024, weeks)
        session.commit()

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
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert [r["gsis_id"] for r in rows] == ["tie-a", "tie-b"]
    assert rows[0]["fantasy_points"] == rows[1]["fantasy_points"]


async def test_non_fantasy_sort_scores_only_page_ids(session_factory, monkeypatch) -> None:
    """Non-fantasy sorts should pass only page player ids to the weekly scorer."""
    _seed(session_factory)
    seen: list[set[str] | None] = []
    original = screener_service._sum_week_fantasy_points

    def tracking_sum(session, season, position, scoring_rules, player_ids=None):
        seen.append(player_ids)
        return original(session, season, position, scoring_rules, player_ids=player_ids)

    monkeypatch.setattr(screener_service, "_sum_week_fantasy_points", tracking_sum)

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "position": "RB",
                    "sort": "rush_yd",
                    "dir": "desc",
                    "limit": 1,
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    assert len(seen) == 1
    assert seen[0] == {"sc-001"}


async def test_synthetic_stored_field_wiring(session_factory) -> None:
    """Nonzero overrides on stored fields not in the slim response must score."""
    players = [
        {"gsis_id": "wire-1", "name": "Wire Player", "position": "RB", "team": "DAL"},
    ]
    weeks = [
        {
            "player_id": "wire-1",
            "week": 1,
            "pass_sack": 2.0,
            "fumble": 1.0,
            "return_yd": 50.0,
            "return_td": 1.0,
            "special_teams_td": 1.0,
            "rush_two_pt": 1.0,
            "pass_two_pt": 1.0,
            "rec_two_pt": 1.0,
        },
    ]
    with session_factory() as session:
        upsert_players(session, players)
        upsert_week_stats(session, 2024, weeks)
        session.commit()

    rules = {
        "pass_sack": -1.0,
        "fumble": -1.0,
        "return_yd": 0.1,
        "return_td": 6.0,
        "special_teams_td": 6.0,
        "rush_two_pt": 2.0,
        "pass_two_pt": 2.0,
        "rec_two_pt": 2.0,
    }
    # Expected: -2 + -1 + 5 + 6 + 6 + 2 + 2 + 2 = 20.0 (standard rec=0 etc.)
    expected = 20.0

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": 2024,
                    "scoring_preset": "standard",
                    "scoring_rules": json.dumps(rules),
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows["wire-1"]["fantasy_points"] == expected


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text())


def _expected_from_fixture_rows(
    source_rows: list[dict],
    gsis_id: str,
    position: str,
    scoring_rules,
) -> float:
    total = 0.0
    for row in source_rows:
        if (row.get("player_id") or "").strip() != gsis_id:
            continue
        mapped = map_week_row(row)
        if mapped is None:
            continue
        stats = PlayerWeekStats(**{col: mapped[col] for col in STAT_COLUMNS})
        total += score_week(stats, scoring_rules, position=position)  # type: ignore[arg-type]
    return round(total, 2)


def _seed_golden(session_factory) -> dict:
    golden = _load_golden()
    season = golden["source"]["season"]
    players = [
        {
            "gsis_id": p["gsis_id"],
            "name": p["name"],
            "position": p["position"],
            "team": "UNK",
        }
        for p in golden["players"]
    ]
    mapped_weeks: list[dict] = []
    for row in golden["rows"]:
        mapped = map_week_row(row)
        if mapped is not None:
            mapped_weeks.append(mapped)

    with session_factory() as session:
        upsert_players(session, players)
        upsert_week_stats(session, season, mapped_weeks)
        session.commit()
    return golden


@pytest.mark.parametrize(
    "gsis_id,position,expected",
    [
        ("00-0026498", "QB", 350.38),
        ("00-0039851", "QB", 350.96),
        ("00-0038542", "RB", 291.8),
        ("00-0033280", "RB", 314.6),
        ("00-0039075", "WR", 246.0),
        ("00-0038543", "WR", 240.9),
        ("00-0037744", "TE", 189.9),
        ("00-0036970", "TE", 122.8),
    ],
)
async def test_golden_replay_standard_totals(
    session_factory,
    gsis_id: str,
    position: str,
    expected: float,
) -> None:
    golden = _seed_golden(session_factory)
    season = golden["source"]["season"]
    standard = scoring_presets.standard().scoring
    independent = _expected_from_fixture_rows(golden["rows"], gsis_id, position, standard)
    assert independent == expected

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": season,
                    "position": position,
                    "scoring_preset": "standard",
                    "sort": "name",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows[gsis_id]["fantasy_points"] == expected
    assert rows[gsis_id]["fantasy_points"] == independent


async def test_bijan_two_point_regression(session_factory) -> None:
    """Bijan rush_two_pt=1 must produce 291.8, not 289.8."""
    golden = _seed_golden(session_factory)
    bijan_rows = [r for r in golden["rows"] if r["player_id"] == "00-0038542"]
    mapped = [map_week_row(r) for r in bijan_rows]
    mapped = [m for m in mapped if m is not None]
    assert sum(m["rush_two_pt"] for m in mapped) == 1.0

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": golden["source"]["season"],
                    "position": "RB",
                    "scoring_preset": "standard",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows["00-0038542"]["fantasy_points"] == 291.8
    assert rows["00-0038542"]["fantasy_points"] != 289.8


async def test_puka_post_filtering_and_games(session_factory) -> None:
    """Puka has 16 REG + 3 POST; POST maps to None; games=16 and 246.0 standard."""
    golden = _seed_golden(session_factory)
    puka_rows = [r for r in golden["rows"] if r["player_id"] == "00-0039075"]
    reg = [r for r in puka_rows if r["season_type"] == "REG"]
    post = [r for r in puka_rows if r["season_type"] == "POST"]
    assert len(reg) == 16
    assert len(post) == 3
    assert all(map_week_row(r) is None for r in post)
    assert all(map_week_row(r) is not None for r in reg)

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": golden["source"]["season"],
                    "position": "WR",
                    "scoring_preset": "standard",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows["00-0039075"]["games"] == 16
    assert rows["00-0039075"]["fantasy_points"] == 246.0


async def test_mcbride_tep(session_factory) -> None:
    """Trey McBride TEP total is 378.9."""
    golden = _seed_golden(session_factory)
    tep_rules = scoring_presets.tight_end_premium().scoring
    independent = _expected_from_fixture_rows(
        golden["rows"],
        "00-0037744",
        "TE",
        tep_rules,
    )
    assert independent == 378.9

    app.dependency_overrides[get_session] = _make_override(session_factory)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/screener",
                params={
                    "season": golden["source"]["season"],
                    "position": "TE",
                    "scoring_preset": "TEP",
                },
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert resp.status_code == 200
    rows = {r["gsis_id"]: r for r in resp.json()["rows"]}
    assert rows["00-0037744"]["fantasy_points"] == 378.9
