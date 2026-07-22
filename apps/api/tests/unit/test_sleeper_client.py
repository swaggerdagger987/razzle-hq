"""Cassette-only unit tests for the keyless Sleeper client."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from razzle_api.ingest import sleeper
from razzle_api.ingest.sleeper import (
    SLEEPER_BASE,
    TTL,
    USER_AGENT,
    SleeperUpstreamError,
    fetch_league,
    fetch_league_snapshot,
    fetch_matchups,
    fetch_nfl_state,
    fetch_rosters,
    fetch_traded_picks,
    fetch_transactions,
    fetch_user,
    fetch_user_leagues,
    fetch_users,
    get_players_nfl,
    sleeper_get,
)

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes" / "sleeper"
LEAGUE_ID = "999888777"
USER_ID = "111222333"
USERNAME = "alice_dynasty"
SEASON = "2025"
PUBLIC_HOST = "api.sleeper.app"


def _load_cassette(relative_path: str) -> Any:
    path = CASSETTES / relative_path
    if not path.is_file():
        raise AssertionError(f"missing cassette fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _path_to_fixture(path: str) -> Path:
    assert path.startswith("/"), path
    return CASSETTES / f"{path.lstrip('/')}.json"


def _cassette_sleeper_get(path: str, *, timeout: float = 30.0) -> Any:
    """Route relative Sleeper paths to on-disk cassettes; reject anything else."""
    if not path.startswith("/") or "://" in path or path.startswith("//"):
        raise AssertionError(f"unrecognized sleeper path (not relative): {path!r}")
    fixture = _path_to_fixture(path)
    if not fixture.is_file():
        raise AssertionError(f"unrecognized public/live Sleeper path: {path}")
    # timeout is part of the transport contract; callers exercise it explicitly.
    assert timeout > 0
    return json.loads(fixture.read_text(encoding="utf-8"))


class _FakeHttpResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.fixture
def cassette_transport(monkeypatch: pytest.MonkeyPatch):
    """Cassette-only sleeper_get plus a hard block on public urlopen."""

    def blocked_urlopen(request, timeout=None):  # noqa: ANN001
        url = request.full_url if hasattr(request, "full_url") else str(request)
        raise AssertionError(f"public/live network call blocked: {url!r} timeout={timeout!r}")

    monkeypatch.setattr(sleeper, "sleeper_get", _cassette_sleeper_get)
    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    return _cassette_sleeper_get


@pytest.fixture
def live_urlopen_guard(monkeypatch: pytest.MonkeyPatch):
    """Block any urlopen that is not explicitly handled by the test body."""

    def blocked_urlopen(request, timeout=None):  # noqa: ANN001
        url = request.full_url if hasattr(request, "full_url") else str(request)
        raise AssertionError(f"public/live network call blocked: {url!r} timeout={timeout!r}")

    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    return blocked_urlopen


def test_sleeper_get_uses_exact_url_headers_and_timeout(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["timeout"] = timeout
        return _FakeHttpResponse(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    payload = sleeper_get("/state/nfl", timeout=12.5)

    assert payload == {"ok": True}
    assert captured["url"] == f"{SLEEPER_BASE}/state/nfl"
    assert captured["headers"]["user-agent"] == USER_AGENT
    assert captured["headers"]["accept"] == "application/json"
    assert captured["timeout"] == 12.5


def test_sleeper_get_rejects_absolute_urls(live_urlopen_guard):
    with pytest.raises(SleeperUpstreamError, match="relative"):
        sleeper_get("https://api.sleeper.app/v1/state/nfl")


def test_sleeper_get_http_error_has_status(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=503,
            msg="Unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SleeperUpstreamError) as excinfo:
        sleeper_get("/state/nfl")
    assert excinfo.value.status_code == 503
    assert "503" in excinfo.value.message


def test_sleeper_get_timeout_error(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        raise TimeoutError("slow")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SleeperUpstreamError, match="timeout") as excinfo:
        sleeper_get("/state/nfl")
    assert excinfo.value.status_code is None


def test_sleeper_get_url_error(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        raise urllib.error.URLError("dns boom")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SleeperUpstreamError, match="URL error") as excinfo:
        sleeper_get("/state/nfl")
    assert excinfo.value.status_code is None


def test_sleeper_get_invalid_json(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        return _FakeHttpResponse(b"not-json")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SleeperUpstreamError, match="invalid JSON"):
        sleeper_get("/state/nfl")


def test_sleeper_get_decode_failure(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        return _FakeHttpResponse(b"\xff\xfe")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SleeperUpstreamError, match="decode"):
        sleeper_get("/state/nfl")


def test_fetch_user_url_encodes_username(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        captured["url"] = request.full_url
        return _FakeHttpResponse(b'{"user_id":"1","username":"a b"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    user = fetch_user("a b/c")
    assert user == {"user_id": "1", "username": "a b"}
    assert captured["url"] == f"{SLEEPER_BASE}/user/a%20b%2Fc"


def test_fetch_user_404_returns_none(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert fetch_user("missing_user") is None


def test_fetch_user_null_returns_none(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        return _FakeHttpResponse(b"null")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert fetch_user("null_user") is None


def test_fetch_league_404_and_null(monkeypatch: pytest.MonkeyPatch):
    def raise_404(request, timeout=None):  # noqa: ANN001
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_404)
    assert fetch_league("nope") is None

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeHttpResponse(b"null"),
    )
    assert fetch_league("null_league") is None


def test_wrong_json_shapes_raise(monkeypatch: pytest.MonkeyPatch):
    responses = {
        f"{SLEEPER_BASE}/state/nfl": b"[]",
        f"{SLEEPER_BASE}/user/x": b'"string"',
        f"{SLEEPER_BASE}/user/1/leagues/nfl/2025": b"{}",
        f"{SLEEPER_BASE}/league/1/rosters": b'[{"ok":1}, "bad"]',
        f"{SLEEPER_BASE}/league/1/users": b"null",
        f"{SLEEPER_BASE}/league/1/matchups/1": b"{}",
        f"{SLEEPER_BASE}/league/1/transactions/0": b"42",
        f"{SLEEPER_BASE}/league/1/traded_picks": b'{"not":"list"}',
    }

    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        body = responses[request.full_url]
        return _FakeHttpResponse(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(SleeperUpstreamError, match="object"):
        fetch_nfl_state()
    with pytest.raises(SleeperUpstreamError, match="object"):
        fetch_user("x")
    with pytest.raises(SleeperUpstreamError, match="list"):
        fetch_user_leagues("1", "2025")
    with pytest.raises(SleeperUpstreamError, match="list of objects"):
        fetch_rosters("1")
    with pytest.raises(SleeperUpstreamError, match="list"):
        fetch_users("1")
    with pytest.raises(SleeperUpstreamError, match="list"):
        fetch_matchups("1", 1)
    with pytest.raises(SleeperUpstreamError, match="list"):
        fetch_transactions("1", 0)
    with pytest.raises(SleeperUpstreamError, match="list"):
        fetch_traded_picks("1")


def test_state_season_used_for_user_leagues(cassette_transport, monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, float]] = []

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append((path, timeout))
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", tracking_get)

    state = fetch_nfl_state()
    assert state["league_season"] == SEASON
    user = fetch_user(USERNAME)
    assert user is not None
    leagues = fetch_user_leagues(user["user_id"], state["league_season"])

    assert leagues[0]["league_id"] == LEAGUE_ID
    assert ("/state/nfl", 30.0) in calls
    assert (f"/user/{USERNAME}", 30.0) in calls
    assert (f"/user/{USER_ID}/leagues/nfl/{SEASON}", 30.0) in calls
    # Calendar year must not be guessed — only league_season appears.
    assert not any("/leagues/nfl/2024" in path for path, _ in calls)
    assert not any("/leagues/nfl/2026" in path for path, _ in calls)


def test_snapshot_complete_and_exact_week_bounds(cassette_transport, monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append(path)
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", tracking_get)

    snapshot = fetch_league_snapshot(LEAGUE_ID)

    assert set(snapshot) == {
        "league",
        "users",
        "rosters",
        "traded_picks",
        "matchups_by_week",
        "transactions_by_week",
        "state",
    }
    assert snapshot["league"] == _load_cassette(f"league/{LEAGUE_ID}.json")
    assert snapshot["users"] == _load_cassette(f"league/{LEAGUE_ID}/users.json")
    assert snapshot["rosters"] == _load_cassette(f"league/{LEAGUE_ID}/rosters.json")
    assert snapshot["traded_picks"] == _load_cassette(f"league/{LEAGUE_ID}/traded_picks.json")
    assert snapshot["state"]["display_week"] == 3

    assert set(snapshot["matchups_by_week"]) == {1, 2, 3}
    for week in (1, 2, 3):
        assert snapshot["matchups_by_week"][week] == _load_cassette(
            f"league/{LEAGUE_ID}/matchups/{week}.json"
        )
        assert f"/league/{LEAGUE_ID}/matchups/{week}" in calls

    assert set(snapshot["transactions_by_week"]) == set(range(0, 19))
    for week in range(0, 19):
        assert snapshot["transactions_by_week"][week] == _load_cassette(
            f"league/{LEAGUE_ID}/transactions/{week}.json"
        )
        assert f"/league/{LEAGUE_ID}/transactions/{week}" in calls

    # No matchups outside 1..display_week (3).
    assert "/league/999888777/matchups/4" not in calls
    assert "/league/999888777/matchups/0" not in calls
    assert "/league/999888777/transactions/19" not in calls


def test_snapshot_uses_provided_state_without_refetch(
    cassette_transport, monkeypatch: pytest.MonkeyPatch
):
    calls: list[str] = []

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append(path)
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", tracking_get)
    state = {"display_week": 1, "week": 9, "league_season": SEASON}
    snapshot = fetch_league_snapshot(LEAGUE_ID, state=state)

    assert "/state/nfl" not in calls
    assert set(snapshot["matchups_by_week"]) == {1}
    assert snapshot["state"] is state


def test_snapshot_missing_league_raises(cassette_transport, monkeypatch: pytest.MonkeyPatch):
    def missing_league(path: str, *, timeout: float = 30.0) -> Any:
        if path.startswith("/league/missing"):
            raise SleeperUpstreamError("Sleeper HTTP 404", status_code=404)
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", missing_league)
    with pytest.raises(SleeperUpstreamError, match="not found") as excinfo:
        fetch_league_snapshot("missing")
    assert excinfo.value.status_code == 404


def test_fresh_cache_skips_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(sleeper, "_utc_now", lambda: now)

    players = {"4046": {"player_id": "4046", "full_name": "Cached"}}
    data_path = tmp_path / "sleeper_players_nfl.json"
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    data_path.write_text(json.dumps(players), encoding="utf-8")
    meta_path.write_text(
        json.dumps({"fetched_at": (now - timedelta(hours=1)).isoformat()}),
        encoding="utf-8",
    )

    def boom(path: str, *, timeout: float = 30.0) -> Any:
        raise AssertionError(f"network should not run for fresh cache: {path}")

    monkeypatch.setattr(sleeper, "sleeper_get", boom)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("live network")),
    )

    loaded = get_players_nfl(cache_dir=tmp_path)
    assert loaded == players


def test_stale_forced_corrupt_missing_cache_refetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(sleeper, "_utc_now", lambda: now)
    cassette_players = _load_cassette("players/nfl.json")
    calls: list[tuple[str, float]] = []

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append((path, timeout))
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", tracking_get)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("live network")),
    )

    # Missing cache.
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    # Fresh — no extra network.
    calls.clear()
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == []

    # Force refresh.
    assert get_players_nfl(cache_dir=tmp_path, force_refresh=True) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    # Stale metadata.
    calls.clear()
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    meta_path.write_text(
        json.dumps({"fetched_at": (now - timedelta(seconds=TTL + 1)).isoformat()}),
        encoding="utf-8",
    )
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    # Corrupt data file.
    calls.clear()
    (tmp_path / "sleeper_players_nfl.json").write_text("{not-json", encoding="utf-8")
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    # Non-dict cache payload.
    calls.clear()
    (tmp_path / "sleeper_players_nfl.json").write_text("[]", encoding="utf-8")
    meta_path.write_text(
        json.dumps({"fetched_at": now.isoformat()}),
        encoding="utf-8",
    )
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]


def test_atomic_cache_files_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2025, 9, 10, 15, 30, 0, tzinfo=UTC)
    monkeypatch.setattr(sleeper, "_utc_now", lambda: now)
    monkeypatch.setattr(sleeper, "sleeper_get", _cassette_sleeper_get)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("live network")),
    )

    players = get_players_nfl(cache_dir=tmp_path)
    data_path = tmp_path / "sleeper_players_nfl.json"
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"

    assert data_path.is_file()
    assert meta_path.is_file()
    assert json.loads(data_path.read_text(encoding="utf-8")) == players
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fetched_at = datetime.fromisoformat(meta["fetched_at"])
    assert fetched_at.tzinfo is not None
    assert fetched_at == now
    # No leftover temp files from atomic writes.
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


def test_non_dict_players_dump_does_not_replace_good_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(sleeper, "_utc_now", lambda: now)

    good = {"4046": {"player_id": "4046", "full_name": "Keep Me"}}
    data_path = tmp_path / "sleeper_players_nfl.json"
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    data_path.write_text(json.dumps(good), encoding="utf-8")
    # Stale so a refresh is attempted.
    meta_path.write_text(
        json.dumps({"fetched_at": (now - timedelta(seconds=TTL + 5)).isoformat()}),
        encoding="utf-8",
    )
    before_data = data_path.read_text(encoding="utf-8")
    before_meta = meta_path.read_text(encoding="utf-8")

    def bad_players(path: str, *, timeout: float = 30.0) -> Any:
        assert path == "/players/nfl"
        assert timeout == 120.0
        return ["not", "a", "dict"]

    monkeypatch.setattr(sleeper, "sleeper_get", bad_players)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("live network")),
    )

    with pytest.raises(SleeperUpstreamError, match="object"):
        get_players_nfl(cache_dir=tmp_path)

    assert data_path.read_text(encoding="utf-8") == before_data
    assert meta_path.read_text(encoding="utf-8") == before_meta


def test_cassette_transport_rejects_unknown_public_paths(cassette_transport):
    with pytest.raises(AssertionError, match="unrecognized public/live"):
        sleeper.sleeper_get("/players/nba")


def test_no_live_network_for_high_level_flow(cassette_transport, monkeypatch: pytest.MonkeyPatch):
    """End-to-end discovery + snapshot never touches urllib/public hosts."""

    def explode(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError(f"live network attempted via urlopen: {args!r} {kwargs!r}")

    monkeypatch.setattr(urllib.request, "urlopen", explode)

    state = fetch_nfl_state()
    user = fetch_user(USERNAME)
    assert user is not None
    leagues = fetch_user_leagues(user["user_id"], state["league_season"])
    assert leagues[0]["league_id"] == LEAGUE_ID
    snapshot = fetch_league_snapshot(LEAGUE_ID, state=state)
    assert snapshot["league"]["league_id"] == LEAGUE_ID
    assert PUBLIC_HOST not in json.dumps(snapshot)
