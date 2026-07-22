"""Cassette-only unit tests for the keyless Sleeper client."""

from __future__ import annotations

import json
import os
import tempfile
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
    assert timeout > 0
    return json.loads(fixture.read_text(encoding="utf-8"))


def _snapshot_transport(calls: list[str]):
    """Cassette-backed transport that fills missing weekly lists with []."""

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append(path)
        fixture = _path_to_fixture(path)
        if fixture.is_file():
            assert timeout > 0
            return json.loads(fixture.read_text(encoding="utf-8"))
        if "/matchups/" in path or "/transactions/" in path:
            return []
        raise AssertionError(f"unrecognized public/live Sleeper path: {path}")

    return tracking_get


class _FakeHttpResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


@pytest.fixture(autouse=True)
def _block_public_urlopen(monkeypatch: pytest.MonkeyPatch):
    """Structural hermeticity: no urllib network unless a test opts in."""

    def blocked_urlopen(request, timeout=None):  # noqa: ANN001
        url = request.full_url if hasattr(request, "full_url") else str(request)
        raise AssertionError(f"public/live network call blocked: {url!r} timeout={timeout!r}")

    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)


@pytest.fixture
def cassette_transport(monkeypatch: pytest.MonkeyPatch):
    """Route high-level fetchers through on-disk cassettes."""
    monkeypatch.setattr(sleeper, "sleeper_get", _cassette_sleeper_get)
    return _cassette_sleeper_get


def test_sleeper_get_uses_exact_url_headers_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
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


@pytest.mark.parametrize(
    "path",
    [
        "https://api.sleeper.app/v1/state/nfl",
        "//api.sleeper.app/v1/state/nfl",
        "/state/../nfl",
        "/./state/nfl",
        "/state/./nfl",
        "/state/nfl/..",
        "/state//nfl",
        "/state/nfl/",
        r"/state\nfl",
        r"..\state",
        "state/nfl",
        "",
    ],
)
def test_sleeper_get_rejects_noncanonical_paths(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[object] = []

    def tracking_urlopen(request, timeout=None):  # noqa: ANN001
        calls.append(request)
        raise AssertionError("urlopen must not run for invalid paths")

    monkeypatch.setattr(urllib.request, "urlopen", tracking_urlopen)
    with pytest.raises(SleeperUpstreamError, match="relative|canonical"):
        sleeper_get(path)
    assert calls == []


def test_sleeper_get_valid_endpoint_paths_still_work(monkeypatch: pytest.MonkeyPatch):
    seen: list[str] = []

    def fake_urlopen(request, timeout=None):  # noqa: ANN001
        seen.append(request.full_url)
        return _FakeHttpResponse(b'{"ok": true}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    for path in (
        "/state/nfl",
        "/user/alice_dynasty",
        "/user/111222333/leagues/nfl/2025",
        "/league/999888777",
        "/league/999888777/rosters",
        "/league/999888777/users",
        "/league/999888777/matchups/1",
        "/league/999888777/transactions/0",
        "/league/999888777/traded_picks",
        "/players/nfl",
    ):
        assert sleeper_get(path) == {"ok": True}
        assert seen[-1] == f"{SLEEPER_BASE}{path}"


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

    def return_null(request, timeout=None):  # noqa: ANN001
        return _FakeHttpResponse(b"null")

    monkeypatch.setattr(urllib.request, "urlopen", return_null)
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


def test_state_season_used_for_user_leagues(
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
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
    assert not any("/leagues/nfl/2024" in path for path, _ in calls)
    assert not any("/leagues/nfl/2026" in path for path, _ in calls)


def test_snapshot_complete_and_exact_week_bounds(
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
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

    assert "/league/999888777/matchups/4" not in calls
    assert "/league/999888777/matchups/0" not in calls
    assert "/league/999888777/transactions/19" not in calls


@pytest.mark.parametrize(
    ("state", "expected_matchup_weeks"),
    [
        ({"display_week": 22, "week": 9, "league_season": SEASON}, list(range(1, 19))),
        ({"display_week": 0, "week": 9, "league_season": SEASON}, [1]),
        ({"week": 2, "league_season": SEASON}, [1, 2]),
        ({"league_season": SEASON}, [1]),
    ],
)
def test_snapshot_matchup_week_clamps(
    state: dict,
    expected_matchup_weeks: list[int],
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []
    monkeypatch.setattr(sleeper, "sleeper_get", _snapshot_transport(calls))

    snapshot = fetch_league_snapshot(LEAGUE_ID, state=state)

    assert list(snapshot["matchups_by_week"]) == expected_matchup_weeks
    assert set(snapshot["matchups_by_week"]) == set(expected_matchup_weeks)
    matchup_routes = [f"/league/{LEAGUE_ID}/matchups/{week}" for week in expected_matchup_weeks]
    assert [c for c in calls if "/matchups/" in c] == matchup_routes
    for week in expected_matchup_weeks:
        assert f"/league/{LEAGUE_ID}/matchups/{week}" in calls
    for week in range(0, 20):
        if week not in expected_matchup_weeks:
            assert f"/league/{LEAGUE_ID}/matchups/{week}" not in calls
    for week in range(0, 19):
        assert f"/league/{LEAGUE_ID}/transactions/{week}" in calls
    assert f"/league/{LEAGUE_ID}/transactions/19" not in calls


def test_snapshot_uses_provided_state_without_refetch(
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
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


def test_snapshot_missing_league_raises(
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
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

    def fixed_now() -> datetime:
        return now

    monkeypatch.setattr(sleeper, "_utc_now", fixed_now)

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

    loaded = get_players_nfl(cache_dir=tmp_path)
    assert loaded == players


def test_stale_forced_corrupt_missing_cache_refetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)

    def fixed_now() -> datetime:
        return now

    monkeypatch.setattr(sleeper, "_utc_now", fixed_now)
    cassette_players = _load_cassette("players/nfl.json")
    calls: list[tuple[str, float]] = []

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append((path, timeout))
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", tracking_get)

    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    calls.clear()
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == []

    assert get_players_nfl(cache_dir=tmp_path, force_refresh=True) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    calls.clear()
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    meta_path.write_text(
        json.dumps({"fetched_at": (now - timedelta(seconds=TTL + 1)).isoformat()}),
        encoding="utf-8",
    )
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    calls.clear()
    (tmp_path / "sleeper_players_nfl.json").write_text("{not-json", encoding="utf-8")
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]

    calls.clear()
    (tmp_path / "sleeper_players_nfl.json").write_text("[]", encoding="utf-8")
    meta_path.write_text(
        json.dumps({"fetched_at": now.isoformat()}),
        encoding="utf-8",
    )
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]


@pytest.mark.parametrize(
    "fetched_at",
    [
        "2025-09-10T12:00:00",  # naive, no timezone
        "not-a-timestamp",
        "",
        1234567890,
        None,
    ],
)
def test_naive_or_malformed_fetched_at_refetches(
    fetched_at: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)

    def fixed_now() -> datetime:
        return now

    monkeypatch.setattr(sleeper, "_utc_now", fixed_now)
    players = {"4046": {"player_id": "4046", "full_name": "Keep"}}
    data_path = tmp_path / "sleeper_players_nfl.json"
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    data_path.write_text(json.dumps(players), encoding="utf-8")
    if fetched_at is None:
        meta_path.write_text(json.dumps({}), encoding="utf-8")
    else:
        meta_path.write_text(json.dumps({"fetched_at": fetched_at}), encoding="utf-8")

    cassette_players = _load_cassette("players/nfl.json")
    calls: list[tuple[str, float]] = []

    def tracking_get(path: str, *, timeout: float = 30.0) -> Any:
        calls.append((path, timeout))
        return _cassette_sleeper_get(path, timeout=timeout)

    monkeypatch.setattr(sleeper, "sleeper_get", tracking_get)
    assert get_players_nfl(cache_dir=tmp_path) == cassette_players
    assert calls == [("/players/nfl", 120.0)]


def test_atomic_cache_files_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2025, 9, 10, 15, 30, 0, tzinfo=UTC)

    def fixed_now() -> datetime:
        return now

    monkeypatch.setattr(sleeper, "_utc_now", fixed_now)
    monkeypatch.setattr(sleeper, "sleeper_get", _cassette_sleeper_get)

    replaces: list[tuple[Path, Path]] = []
    mkstemp_dirs: list[Path] = []
    real_replace = os.replace
    real_mkstemp = tempfile.mkstemp

    def spy_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        replaces.append((Path(src), Path(dst)))
        real_replace(src, dst)

    def spy_mkstemp(*args: Any, **kwargs: Any) -> tuple[int, str]:
        directory = kwargs.get("dir")
        if directory is None and len(args) >= 3:
            directory = args[2]
        assert directory is not None
        mkstemp_dirs.append(Path(directory))
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(sleeper.os, "replace", spy_replace)
    monkeypatch.setattr(sleeper.tempfile, "mkstemp", spy_mkstemp)

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

    assert mkstemp_dirs == [tmp_path, tmp_path]
    assert len(replaces) == 2
    assert replaces[0][1] == data_path
    assert replaces[1][1] == meta_path
    for src, dst in replaces:
        assert src.parent == dst.parent == tmp_path
        assert src.name.startswith(".")
        assert src.name.endswith(".tmp")
        assert not src.exists()

    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


def test_atomic_write_replace_failure_preserves_target_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)

    def fixed_now() -> datetime:
        return now

    monkeypatch.setattr(sleeper, "_utc_now", fixed_now)

    good = {"4046": {"player_id": "4046", "full_name": "Keep Me"}}
    data_path = tmp_path / "sleeper_players_nfl.json"
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    data_path.write_text(json.dumps(good), encoding="utf-8")
    meta_path.write_text(
        json.dumps({"fetched_at": (now - timedelta(hours=1)).isoformat()}),
        encoding="utf-8",
    )
    before_data = data_path.read_text(encoding="utf-8")
    before_meta = meta_path.read_text(encoding="utf-8")

    monkeypatch.setattr(sleeper, "sleeper_get", _cassette_sleeper_get)

    temps_seen: list[Path] = []

    def failing_replace(
        src: str | os.PathLike[str],
        dst: str | os.PathLike[str],
    ) -> None:
        src_path = Path(src)
        temps_seen.append(src_path)
        assert src_path.parent == tmp_path
        assert src_path.exists()
        raise OSError("simulated replace failure")

    monkeypatch.setattr(sleeper.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        get_players_nfl(cache_dir=tmp_path, force_refresh=True)

    assert data_path.read_text(encoding="utf-8") == before_data
    assert meta_path.read_text(encoding="utf-8") == before_meta
    assert temps_seen
    for temp in temps_seen:
        assert not temp.exists()
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []
    # Pair is not one transaction — failure on first (data) replace never
    # mutates either target file.


def test_non_dict_players_dump_does_not_replace_good_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime(2025, 9, 10, 12, 0, 0, tzinfo=UTC)

    def fixed_now() -> datetime:
        return now

    monkeypatch.setattr(sleeper, "_utc_now", fixed_now)

    good = {"4046": {"player_id": "4046", "full_name": "Keep Me"}}
    data_path = tmp_path / "sleeper_players_nfl.json"
    meta_path = tmp_path / "sleeper_players_nfl.meta.json"
    data_path.write_text(json.dumps(good), encoding="utf-8")
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

    with pytest.raises(SleeperUpstreamError, match="object"):
        get_players_nfl(cache_dir=tmp_path)

    assert data_path.read_text(encoding="utf-8") == before_data
    assert meta_path.read_text(encoding="utf-8") == before_meta


def test_cassette_transport_rejects_unknown_public_paths(cassette_transport):
    with pytest.raises(AssertionError, match="unrecognized public/live"):
        sleeper.sleeper_get("/players/nba")


def test_unrecognized_route_fails_before_network(monkeypatch: pytest.MonkeyPatch):
    urlopen_calls: list[object] = []

    def tracking_urlopen(request, timeout=None):  # noqa: ANN001
        urlopen_calls.append(request)
        raise AssertionError("should not reach urlopen")

    monkeypatch.setattr(urllib.request, "urlopen", tracking_urlopen)
    monkeypatch.setattr(sleeper, "sleeper_get", _cassette_sleeper_get)

    with pytest.raises(AssertionError, match="unrecognized public/live"):
        sleeper.sleeper_get("/players/nba")
    assert urlopen_calls == []


def test_no_live_network_for_high_level_flow(
    cassette_transport,
    monkeypatch: pytest.MonkeyPatch,
):
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
