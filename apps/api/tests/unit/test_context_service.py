"""Unit tests for immutable league context service."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from razzle_api.api.schemas.context import ConnectResponse, ContextRevisionResponse
from razzle_api.config import get_settings
from razzle_api.core.db import get_session
from razzle_api.domain.scoring import compile_league
from razzle_api.ingest.sleeper import SleeperUpstreamError
from razzle_api.main import app
from razzle_api.services import context_service
from razzle_api.services.context_service import (
    ContextForbiddenError,
    ContextNotFoundError,
    ContextUpstreamError,
    connect_username,
    context_revisions_table,
    get_revision,
    leagues_table,
    refresh_league,
)

API_DIR = Path(__file__).resolve().parents[2]
CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes" / "sleeper"
LEAGUE_ID = "999888777"
USER_ID = "111222333"
USERNAME = "alice_dynasty"
SEASON = 2025


def _load_cassette(relative_path: str) -> Any:
    path = CASSETTES / relative_path
    if not path.is_file():
        raise AssertionError(f"missing cassette fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _path_to_fixture(path: str) -> Path:
    assert path.startswith("/"), path
    return CASSETTES / f"{path.lstrip('/')}.json"


def _cassette_sleeper_get(path: str, *, timeout: float = 30.0) -> Any:
    if not path.startswith("/") or "://" in path or path.startswith("//"):
        raise AssertionError(f"unrecognized sleeper path (not relative): {path!r}")
    fixture = _path_to_fixture(path)
    if not fixture.is_file():
        raise AssertionError(f"unrecognized public/live Sleeper path: {path}")
    assert timeout > 0
    return json.loads(fixture.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _block_public_urlopen(monkeypatch: pytest.MonkeyPatch):
    def blocked_urlopen(request, timeout=None):  # noqa: ANN001
        url = request.full_url if hasattr(request, "full_url") else str(request)
        raise AssertionError(f"public/live network call blocked: {url!r} timeout={timeout!r}")

    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)


@pytest.fixture
def cassette_transport(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(context_service.sleeper, "sleeper_get", _cassette_sleeper_get)
    return _cassette_sleeper_get


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'context.db'}"
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


@pytest.fixture
def session(session_factory) -> Session:
    with session_factory() as db:
        yield db


def _revision_count(session: Session, league_id: str | None = None) -> int:
    query = sa.select(sa.func.count()).select_from(context_revisions_table)
    if league_id is not None:
        query = query.where(context_revisions_table.c.league_id == league_id)
    return int(session.execute(query).scalar_one())


def _league_row(session: Session, league_id: str) -> dict | None:
    row = (
        session.execute(sa.select(leagues_table).where(leagues_table.c.league_id == league_id))
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def _revision_row(session: Session, revision_id: str) -> dict | None:
    row = (
        session.execute(
            sa.select(context_revisions_table).where(context_revisions_table.c.id == revision_id)
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def _assert_no_writes(session: Session) -> None:
    assert _revision_count(session) == 0
    assert session.execute(sa.select(sa.func.count()).select_from(leagues_table)).scalar_one() == 0


def test_connect_unknown_user(session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(context_service.sleeper, "fetch_user", lambda username: None)
    with pytest.raises(ContextNotFoundError):
        connect_username(session, "missing_user")
    assert _revision_count(session) == 0
    assert session.execute(sa.select(sa.func.count()).select_from(leagues_table)).scalar_one() == 0


def test_connect_empty_leagues(session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user",
        lambda username: {"user_id": USER_ID, "username": username},
    )
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_nfl_state",
        lambda: {"league_season": "2025"},
    )
    monkeypatch.setattr(context_service.sleeper, "fetch_user_leagues", lambda *a, **k: [])

    payload = connect_username(session, USERNAME)

    assert payload["user"]["user_id"] == USER_ID
    assert payload["season"] == SEASON
    assert payload["leagues"] == []
    assert payload["meta"].get("revision") is None
    assert payload["meta"]["sources"][0]["name"] == "sleeper"
    assert payload["meta"]["assumptions"] == ["explicitly owned leagues"]
    assert _revision_count(session) == 0


def test_connect_owned_leagues(session: Session, cassette_transport):
    payload = connect_username(session, USERNAME)

    assert payload["user"]["user_id"] == USER_ID
    assert payload["user"]["username"] == USERNAME
    assert payload["season"] == SEASON
    assert len(payload["leagues"]) == 1
    summary = payload["leagues"][0]
    assert summary == {
        "league_id": LEAGUE_ID,
        "name": "Pixel Punchers",
        "season": SEASON,
        "sport": "nfl",
        "total_rosters": 12,
    }
    assert "scoring_settings" not in summary
    assert payload["meta"]["sources"][0]["name"] == "sleeper"
    assert payload["meta"]["assumptions"] == ["explicitly owned leagues"]
    as_of = payload["meta"]["sources"][0]["as_of"]
    assert as_of.endswith("Z")
    assert _revision_count(session) == 0


def test_connect_upstream_no_writes(session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user",
        lambda username: (_ for _ in ()).throw(SleeperUpstreamError("boom", status_code=503)),
    )
    with pytest.raises(ContextUpstreamError, match="boom"):
        connect_username(session, USERNAME)
    assert _revision_count(session) == 0
    assert session.execute(sa.select(sa.func.count()).select_from(leagues_table)).scalar_one() == 0


def test_refresh_foreign_ownership(session: Session, cassette_transport, monkeypatch):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user_leagues",
        lambda *a, **k: [{"league_id": "other-league", "name": "No", "season": "2025"}],
    )
    with pytest.raises(ContextForbiddenError):
        refresh_league(session, LEAGUE_ID, username=USERNAME)
    assert _revision_count(session) == 0
    assert _league_row(session, LEAGUE_ID) is None


def test_two_immutable_revisions_monotonic_and_old_unchanged(
    session: Session,
    cassette_transport,
):
    first = refresh_league(session, LEAGUE_ID, username=USERNAME)
    first_row = _revision_row(session, first["revision_id"])
    assert first_row is not None
    first_snapshot = first_row["snapshot_json"]
    first_revision_no = first_row["revision"]

    second = refresh_league(session, LEAGUE_ID, username=USERNAME)
    second_row = _revision_row(session, second["revision_id"])
    assert second_row is not None

    assert first["revision_id"] != second["revision_id"]
    assert second_row["revision"] == first_revision_no + 1
    assert _revision_row(session, first["revision_id"])["snapshot_json"] == first_snapshot
    assert _revision_count(session, LEAGUE_ID) == 2


def test_refresh_complete_snapshot(session: Session, cassette_transport):
    payload = refresh_league(session, LEAGUE_ID, username=USERNAME)

    assert payload["league_id"] == LEAGUE_ID
    assert payload["season"] == SEASON
    assert payload["league"] == _load_cassette(f"league/{LEAGUE_ID}.json")
    assert payload["users"] == _load_cassette(f"league/{LEAGUE_ID}/users.json")
    assert payload["rosters"] == _load_cassette(f"league/{LEAGUE_ID}/rosters.json")
    assert payload["traded_picks"] == _load_cassette(f"league/{LEAGUE_ID}/traded_picks.json")
    assert set(payload["matchups_by_week"]) == {1, 2, 3}
    assert set(payload["transactions_by_week"]) == set(range(0, 19))
    assert payload["state"]["league_season"] == "2025"
    assert payload["meta"]["revision"] == payload["revision_id"]
    assert payload["meta"]["sources"][0]["name"] == "sleeper"


def test_partial_coverage_visible(session: Session, cassette_transport, monkeypatch):
    base_snapshot = context_service.sleeper.fetch_league_snapshot(LEAGUE_ID)

    def partial_snapshot(league_id: str, *, state=None):  # noqa: ANN001
        snap = dict(base_snapshot)
        league = dict(snap["league"])
        scoring = dict(league.get("scoring_settings") or {})
        scoring["mystery_stat"] = 3.0
        league["scoring_settings"] = scoring
        snap["league"] = league
        return snap

    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", partial_snapshot)

    payload = refresh_league(session, LEAGUE_ID, username=USERNAME)

    assert payload["coverage"]["status"] == "partial"
    assert any(item["key"] == "mystery_stat" for item in payload["coverage"]["unsupported_keys"])
    assert payload["compiled_rules"]["coverage"] == payload["coverage"]


def test_league_upsert_same_transaction(
    session: Session,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    first = refresh_league(session, LEAGUE_ID, username=USERNAME)
    league = _league_row(session, LEAGUE_ID)
    assert league is not None
    created_at = league["created_at"]
    assert league["name"] == "Pixel Punchers"
    assert league["season"] == SEASON

    real_fetch = context_service.sleeper.fetch_league_snapshot

    def renamed_fetch(league_id: str, *, state=None):  # noqa: ANN001
        snap = real_fetch(league_id, state=state)
        league_payload = dict(snap["league"])
        league_payload["name"] = "Renamed Punchers"
        snap["league"] = league_payload
        return snap

    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", renamed_fetch)
    second = refresh_league(session, LEAGUE_ID, username=USERNAME)

    league_after = _league_row(session, LEAGUE_ID)
    assert league_after is not None
    assert league_after["created_at"] == created_at
    assert league_after["name"] == "Renamed Punchers"
    assert league_after["updated_at"] >= created_at
    assert second["revision_id"] != first["revision_id"]
    assert _revision_count(session, LEAGUE_ID) == 2


def test_upstream_failure_revision_count_unchanged(
    session: Session, cassette_transport, monkeypatch
):
    first = refresh_league(session, LEAGUE_ID, username=USERNAME)
    assert _revision_count(session, LEAGUE_ID) == 1

    def boom(league_id: str, *, state=None):  # noqa: ANN001
        raise SleeperUpstreamError("snapshot failed", status_code=503)

    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", boom)
    with pytest.raises(ContextUpstreamError, match="snapshot failed"):
        refresh_league(session, LEAGUE_ID, username=USERNAME)

    assert _revision_count(session, LEAGUE_ID) == 1
    assert _revision_row(session, first["revision_id"]) is not None


def test_json_int_week_keys_roundtrip(session: Session, cassette_transport):
    created = refresh_league(session, LEAGUE_ID, username=USERNAME)
    assert all(isinstance(key, int) for key in created["matchups_by_week"])
    assert all(isinstance(key, int) for key in created["transactions_by_week"])

    stored = _revision_row(session, created["revision_id"])
    assert stored is not None
    raw_snapshot = json.loads(stored["snapshot_json"])
    assert all(isinstance(key, str) for key in raw_snapshot["matchups_by_week"])

    loaded = get_revision(session, created["revision_id"])
    assert loaded is not None
    assert set(loaded["matchups_by_week"]) == {1, 2, 3}
    assert all(isinstance(key, int) for key in loaded["matchups_by_week"])
    assert all(isinstance(key, int) for key in loaded["transactions_by_week"])


def test_compiled_coverage_consistency(session: Session, cassette_transport):
    payload = refresh_league(session, LEAGUE_ID, username=USERNAME)
    expected = compile_league(payload["league"])
    assert payload["compiled_rules"] == expected.model_dump(mode="json")
    assert payload["coverage"] == expected.coverage.model_dump(mode="json")
    assert payload["compiled_rules"]["coverage"] == payload["coverage"]


def test_source_meta_utc(session: Session, cassette_transport):
    payload = refresh_league(session, LEAGUE_ID, username=USERNAME)
    assert payload["created_at"].tzinfo is not None
    assert payload["created_at"].utcoffset() == UTC.utcoffset(payload["created_at"])
    as_of = payload["meta"]["sources"][0]["as_of"]
    assert as_of.endswith("Z")
    parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None

    sources_json = _revision_row(session, payload["revision_id"])["sources_json"]
    sources = json.loads(sources_json)
    assert isinstance(sources, list)
    assert sources[0]["name"] == "sleeper"


def test_get_unknown_revision(session: Session):
    assert get_revision(session, "does-not-exist") is None


def test_get_offline_no_sleeper(session: Session, cassette_transport, monkeypatch):
    created = refresh_league(session, LEAGUE_ID, username=USERNAME)

    def blocked(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("get_revision must not call sleeper")

    for name in (
        "fetch_user",
        "fetch_nfl_state",
        "fetch_user_leagues",
        "fetch_league_snapshot",
        "sleeper_get",
    ):
        monkeypatch.setattr(context_service.sleeper, name, blocked)

    loaded = get_revision(session, created["revision_id"])
    assert loaded is not None
    assert loaded["revision_id"] == created["revision_id"]
    assert loaded["meta"]["revision"] == created["revision_id"]
    assert loaded["league"] == created["league"]
    assert loaded["coverage"] == created["coverage"]


def test_persistence_retry_on_unique_race(session: Session, cassette_transport, monkeypatch):
    attempts = {"n": 0}
    real_commit = Session.commit

    def flaky_commit(self):  # noqa: ANN001
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise IntegrityError("statement", {}, Exception("unique"))
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)
    payload = refresh_league(session, LEAGUE_ID, username=USERNAME)
    assert attempts["n"] == 2
    assert _revision_count(session, LEAGUE_ID) == 1
    assert get_revision(session, payload["revision_id"]) is not None


def test_refresh_network_before_db(session: Session, cassette_transport, monkeypatch):
    order: list[str] = []

    real_fetch_user = context_service.sleeper.fetch_user
    real_fetch_state = context_service.sleeper.fetch_nfl_state
    real_fetch_leagues = context_service.sleeper.fetch_user_leagues
    real_fetch_snapshot = context_service.sleeper.fetch_league_snapshot
    real_upsert = context_service._upsert_league

    def wrap_user(username: str):
        order.append("user")
        return real_fetch_user(username)

    def wrap_state():
        order.append("state")
        return real_fetch_state()

    def wrap_leagues(user_id: str, season: str | int):
        order.append("leagues")
        return real_fetch_leagues(user_id, season)

    def wrap_snapshot(league_id: str, *, state=None):  # noqa: ANN001
        order.append("snapshot")
        return real_fetch_snapshot(league_id, state=state)

    def wrap_upsert(*args, **kwargs):
        order.append("db")
        return real_upsert(*args, **kwargs)

    monkeypatch.setattr(context_service.sleeper, "fetch_user", wrap_user)
    monkeypatch.setattr(context_service.sleeper, "fetch_nfl_state", wrap_state)
    monkeypatch.setattr(context_service.sleeper, "fetch_user_leagues", wrap_leagues)
    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", wrap_snapshot)
    monkeypatch.setattr(context_service, "_upsert_league", wrap_upsert)

    refresh_league(session, LEAGUE_ID, username=USERNAME)
    assert order == ["user", "state", "leagues", "snapshot", "db"]


def test_service_payloads_validate_typed_schemas(session: Session, cassette_transport):
    connect_payload = connect_username(session, USERNAME)
    connect_model = ConnectResponse.model_validate(connect_payload)
    assert connect_model.meta.revision is None

    refresh_payload = refresh_league(session, LEAGUE_ID, username=USERNAME)
    revision_model = ContextRevisionResponse.model_validate(refresh_payload)
    assert revision_model.coverage.status in {"full", "partial"}
    assert revision_model.compiled_rules.coverage == revision_model.coverage

    loaded = get_revision(session, refresh_payload["revision_id"])
    assert loaded is not None
    ContextRevisionResponse.model_validate(loaded)


def test_schema_rejects_garbage_coverage(session: Session, cassette_transport):
    payload = refresh_league(session, LEAGUE_ID, username=USERNAME)
    ContextRevisionResponse.model_validate(payload)

    garbage_cases = (
        {"status": "nope"},
        {"status": "partial", "unsupported_keys": "not-a-list"},
        {"status": "full", "invented": True},
        "not-an-object",
        None,
    )
    for garbage in garbage_cases:
        bad = dict(payload)
        bad["coverage"] = garbage
        with pytest.raises(ValidationError):
            ContextRevisionResponse.model_validate(bad)

        bad_rules = dict(payload)
        bad_rules["compiled_rules"] = {**payload["compiled_rules"], "coverage": garbage}
        with pytest.raises(ValidationError):
            ContextRevisionResponse.model_validate(bad_rules)


@pytest.mark.parametrize(
    "user",
    [
        {"username": USERNAME},
        {"user_id": 111222333, "username": USERNAME},
        {"user_id": "", "username": USERNAME},
        {"user_id": None, "username": USERNAME},
    ],
)
def test_bad_user_id_is_upstream_no_writes(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    user: dict,
):
    monkeypatch.setattr(context_service.sleeper, "fetch_user", lambda username: user)
    with pytest.raises(ContextUpstreamError, match="user_id"):
        connect_username(session, USERNAME)
    _assert_no_writes(session)


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"league_season": None},
        {"league_season": "autumn"},
        {"league_season": True},
        ["not-an-object"],
    ],
)
def test_bad_state_season_is_upstream_no_writes(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    state: object,
):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user",
        lambda username: {"user_id": USER_ID, "username": USERNAME},
    )
    monkeypatch.setattr(context_service.sleeper, "fetch_nfl_state", lambda: state)
    with pytest.raises(ContextUpstreamError):
        connect_username(session, USERNAME)
    _assert_no_writes(session)


_MALFORMED_LEAGUES = [
    None,
    {"league_id": LEAGUE_ID},
    "not-a-list",
    [None],
    ["scalar"],
    [{"name": "No ID"}],
    [{"league_id": ""}],
    [{"league_id": "   "}],
    [{"league_id": 123}],
]


def _patch_owned_leagues(monkeypatch: pytest.MonkeyPatch, leagues: object) -> None:
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user",
        lambda username: {"user_id": USER_ID, "username": USERNAME},
    )
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_nfl_state",
        lambda: {"league_season": "2025"},
    )
    monkeypatch.setattr(context_service.sleeper, "fetch_user_leagues", lambda *a, **k: leagues)


@pytest.mark.parametrize("leagues", _MALFORMED_LEAGUES)
def test_malformed_owned_leagues_is_upstream_no_writes(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    leagues: object,
):
    _patch_owned_leagues(monkeypatch, leagues)

    with pytest.raises(ContextUpstreamError, match="owned league"):
        connect_username(session, USERNAME)
    _assert_no_writes(session)

    with pytest.raises(ContextUpstreamError, match="owned league"):
        refresh_league(session, LEAGUE_ID, username=USERNAME)
    _assert_no_writes(session)


async def test_malformed_owned_leagues_http_502_no_writes(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_owned_leagues(monkeypatch, [{"name": "No ID"}])

    def override_session():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_session] = override_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            connect = await client.post("/api/context/connect", json={"username": USERNAME})
            refresh = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert connect.status_code == 502
    assert refresh.status_code == 502
    with session_factory() as db:
        _assert_no_writes(db)


def _drop_league(snap: dict) -> dict:
    del snap["league"]
    return snap


def _wrong_league_payload(snap: dict) -> dict:
    snap["league"] = "nope"
    return snap


def _nonnumeric_season(snap: dict) -> dict:
    snap["league"]["season"] = "autumn"
    return snap


def _null_season(snap: dict) -> dict:
    snap["league"]["season"] = None
    return snap


def _drop_users(snap: dict) -> dict:
    del snap["users"]
    return snap


@pytest.mark.parametrize(
    "mutate",
    [
        _drop_league,
        _wrong_league_payload,
        _nonnumeric_season,
        _null_season,
        _drop_users,
    ],
)
def test_bad_snapshot_is_upstream_no_writes(
    session: Session,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
):
    real_fetch = context_service.sleeper.fetch_league_snapshot

    def bad_snapshot(league_id: str, *, state=None):  # noqa: ANN001
        snap = dict(real_fetch(league_id, state=state))
        snap["league"] = dict(snap["league"])
        return mutate(snap)

    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", bad_snapshot)
    with pytest.raises(ContextUpstreamError):
        refresh_league(session, LEAGUE_ID, username=USERNAME)
    _assert_no_writes(session)
