"""Integration tests for context connect / refresh / revision routes."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from razzle_api.config import get_settings
from razzle_api.core.db import get_session
from razzle_api.ingest.sleeper import SleeperUpstreamError
from razzle_api.main import app
from razzle_api.services import context_service

API_DIR = Path(__file__).resolve().parents[2]
CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes" / "sleeper"
LEAGUE_ID = "999888777"
USERNAME = "alice_dynasty"


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
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'context_api.db'}"
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
def cassette_transport(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(context_service.sleeper, "sleeper_get", _cassette_sleeper_get)
    return _cassette_sleeper_get


def _override_session(session_factory):
    def override_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session


def _clear_override() -> None:
    app.dependency_overrides.pop(get_session, None)


def _revision_count(session_factory) -> int:
    with session_factory() as session:
        return int(session.execute(sa.text("SELECT COUNT(*) FROM context_revisions")).scalar_one())


def _league_count(session_factory) -> int:
    with session_factory() as session:
        return int(session.execute(sa.text("SELECT COUNT(*) FROM leagues")).scalar_one())


def _assert_meta_optional_absence(meta: dict) -> None:
    assert "revision" not in meta
    assert "coverage" not in meta
    assert "model_version" not in meta


async def test_connect_refresh_get_cassette_flow(session_factory, cassette_transport):
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            connect = await client.post("/api/context/connect", json={"username": USERNAME})
            assert connect.status_code == 200
            connect_body = connect.json()
            assert connect_body["user"]["username"] == USERNAME
            assert connect_body["season"] == 2025
            assert connect_body["leagues"][0]["league_id"] == LEAGUE_ID
            assert connect_body["meta"]["assumptions"] == ["explicitly owned leagues"]
            _assert_meta_optional_absence(connect_body["meta"])
            assert connect_body["meta"]["sources"][0]["name"] == "sleeper"
            assert connect_body["meta"]["sources"][0]["as_of"].endswith("Z")

            refresh = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
            assert refresh.status_code == 200
            refresh_body = refresh.json()
            revision_id = refresh_body["revision_id"]
            assert refresh_body["league_id"] == LEAGUE_ID
            assert refresh_body["season"] == 2025
            assert refresh_body["meta"]["revision"] == revision_id
            assert refresh_body["meta"]["sources"][0]["name"] == "sleeper"
            assert refresh_body["coverage"]["status"] in {"full", "partial"}
            assert refresh_body["compiled_rules"]["coverage"] == refresh_body["coverage"]
            assert refresh_body["meta"]["coverage"] == refresh_body["coverage"]
            assert "model_version" not in refresh_body["meta"]
            assert {int(k) for k in refresh_body["matchups_by_week"]} == {1, 2, 3}
            assert _revision_count(session_factory) == 1

            got = await client.get(f"/api/context/revision/{revision_id}")
            assert got.status_code == 200
            got_body = got.json()
            assert got_body["revision_id"] == revision_id
            assert got_body["meta"]["revision"] == revision_id
            assert got_body["league"] == refresh_body["league"]
            assert got_body["coverage"] == refresh_body["coverage"]
            assert got_body["compiled_rules"]["coverage"] == got_body["coverage"]
            assert {int(k) for k in got_body["matchups_by_week"]} == {1, 2, 3}
    finally:
        _clear_override()


async def test_refresh_partial_coverage_http(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    real_fetch = context_service.sleeper.fetch_league_snapshot

    def partial_snapshot(league_id: str, *, state=None):  # noqa: ANN001
        snap = dict(real_fetch(league_id, state=state))
        league = dict(snap["league"])
        scoring = dict(league.get("scoring_settings") or {})
        scoring["mystery_stat"] = 3.0
        league["scoring_settings"] = scoring
        snap["league"] = league
        return snap

    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", partial_snapshot)
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
    finally:
        _clear_override()

    assert response.status_code == 200
    body = response.json()
    assert body["coverage"]["status"] == "partial"
    unsupported = body["coverage"]["unsupported_keys"]
    assert any(item["key"] == "mystery_stat" for item in unsupported)
    assert body["compiled_rules"]["coverage"] == body["coverage"]
    assert body["meta"]["coverage"] == body["coverage"]
    assert body["compiled_rules"]["coverage"]["unsupported_keys"] == unsupported


def _schema_ref_name(node: dict[str, Any]) -> str:
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    for item in node.get("allOf", []):
        if isinstance(item, dict) and "$ref" in item:
            return item["$ref"].rsplit("/", 1)[-1]
    raise AssertionError(f"schema node missing $ref: {node}")


async def test_openapi_exposes_compiled_rules_and_coverage_types():
    schema = app.openapi()
    components = schema["components"]["schemas"]
    assert "CompiledRules" in components
    assert "CoverageReport" in components
    assert "UnsupportedScoringKey" in components

    refresh_schema = schema["paths"]["/api/context/leagues/{league_id}/refresh"]["post"]
    response_schema = refresh_schema["responses"]["200"]["content"]["application/json"]["schema"]
    revision = components[_schema_ref_name(response_schema)]
    props = revision["properties"]
    assert _schema_ref_name(props["compiled_rules"]) == "CompiledRules"
    assert _schema_ref_name(props["coverage"]) == "CoverageReport"

    get_schema = schema["paths"]["/api/context/revision/{revision_id}"]["get"]
    get_response = get_schema["responses"]["200"]["content"]["application/json"]["schema"]
    get_props = components[_schema_ref_name(get_response)]["properties"]
    assert _schema_ref_name(get_props["compiled_rules"]) == "CompiledRules"
    assert _schema_ref_name(get_props["coverage"]) == "CoverageReport"


async def test_refresh_foreign_league_403(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user_leagues",
        lambda *a, **k: [{"league_id": "someone-else", "name": "Nope", "season": "2025"}],
    )
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
    finally:
        _clear_override()
    assert response.status_code == 403
    assert _revision_count(session_factory) == 0


async def test_connect_unknown_user_404(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_service.sleeper, "fetch_user", lambda username: None)
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/context/connect", json={"username": "ghost"})
    finally:
        _clear_override()
    assert response.status_code == 404


async def test_refresh_unknown_user_404(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_service.sleeper, "fetch_user", lambda username: None)
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": "ghost"},
            )
    finally:
        _clear_override()
    assert response.status_code == 404
    assert _revision_count(session_factory) == 0
    assert _league_count(session_factory) == 0


async def test_revision_unknown_404(session_factory, cassette_transport):
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/context/revision/missing-revision")
    finally:
        _clear_override()
    assert response.status_code == 404


async def test_refresh_upstream_502_no_partial(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_league_snapshot",
        lambda *a, **k: (_ for _ in ()).throw(
            SleeperUpstreamError("upstream down", status_code=503)
        ),
    )
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
    finally:
        _clear_override()
    assert response.status_code == 502
    assert _revision_count(session_factory) == 0


async def test_connect_upstream_502(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user",
        lambda username: (_ for _ in ()).throw(SleeperUpstreamError("down", status_code=503)),
    )
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/context/connect", json={"username": USERNAME})
    finally:
        _clear_override()
    assert response.status_code == 502
    assert _revision_count(session_factory) == 0
    assert _league_count(session_factory) == 0


async def test_bad_user_id_http_502_no_writes(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        context_service.sleeper,
        "fetch_user",
        lambda username: {"username": USERNAME},
    )
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            connect = await client.post("/api/context/connect", json={"username": USERNAME})
            refresh = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
    finally:
        _clear_override()
    assert connect.status_code == 502
    assert refresh.status_code == 502
    assert _revision_count(session_factory) == 0
    assert _league_count(session_factory) == 0


async def test_bad_snapshot_season_http_502_no_writes(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    real_fetch = context_service.sleeper.fetch_league_snapshot

    def bad_season(league_id: str, *, state=None):  # noqa: ANN001
        snap = dict(real_fetch(league_id, state=state))
        league = dict(snap["league"])
        league["season"] = "autumn"
        snap["league"] = league
        return snap

    monkeypatch.setattr(context_service.sleeper, "fetch_league_snapshot", bad_season)
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
    finally:
        _clear_override()
    assert response.status_code == 502
    assert _revision_count(session_factory) == 0
    assert _league_count(session_factory) == 0


async def test_get_revision_network_blocked(
    session_factory,
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            refresh = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME},
            )
            assert refresh.status_code == 200
            revision_id = refresh.json()["revision_id"]

            def blocked(*args, **kwargs):  # noqa: ANN001
                raise AssertionError("GET revision must not call sleeper")

            for name in (
                "fetch_user",
                "fetch_nfl_state",
                "fetch_user_leagues",
                "fetch_league_snapshot",
                "sleeper_get",
            ):
                monkeypatch.setattr(context_service.sleeper, name, blocked)

            response = await client.get(f"/api/context/revision/{revision_id}")
            assert response.status_code == 200
            body = response.json()
            assert body["revision_id"] == revision_id
            assert body["meta"]["revision"] == revision_id
    finally:
        _clear_override()


async def test_connect_validation_422(session_factory, cassette_transport):
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            empty = await client.post("/api/context/connect", json={"username": "   "})
            assert empty.status_code == 422
            missing = await client.post("/api/context/connect", json={})
            assert missing.status_code == 422
            extra = await client.post(
                "/api/context/connect",
                json={"username": USERNAME, "extra": True},
            )
            assert extra.status_code == 422
    finally:
        _clear_override()


async def test_refresh_validation_422(session_factory, cassette_transport):
    _override_session(session_factory)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            empty_user = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": "   "},
            )
            assert empty_user.status_code == 422
            missing = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={},
            )
            assert missing.status_code == 422
            extra = await client.post(
                f"/api/context/leagues/{LEAGUE_ID}/refresh",
                json={"username": USERNAME, "extra": True},
            )
            assert extra.status_code == 422
    finally:
        _clear_override()
    assert _revision_count(session_factory) == 0
