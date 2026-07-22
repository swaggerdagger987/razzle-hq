"""Keyless Sleeper HTTP client.

Production is live-only. Pytest must never reach public Sleeper — tests inject
a cassette transport (or fail any unrecognized network call).
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SLEEPER_BASE = "https://api.sleeper.app/v1"
USER_AGENT = "razzle-sync/1.0"
TTL = 86400

_PLAYERS_CACHE_NAME = "sleeper_players_nfl.json"
_PLAYERS_META_NAME = "sleeper_players_nfl.meta.json"
_PLAYERS_TIMEOUT = 120.0

_utc_now: Callable[[], datetime] = lambda: datetime.now(UTC)


class SleeperUpstreamError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _default_cache_dir() -> Path:
    # apps/api/src/razzle_api/ingest/sleeper.py -> repo root
    return Path(__file__).resolve().parents[5] / "data" / "cache"


def _require_relative_path(path: str) -> str:
    if not path or not path.startswith("/") or path.startswith("//"):
        raise SleeperUpstreamError(f"Sleeper path must be relative (got {path!r})")
    if "://" in path:
        raise SleeperUpstreamError(f"Sleeper path must be relative (got {path!r})")
    return path


def sleeper_get(path: str, *, timeout: float = 30.0) -> Any:
    """GET a relative Sleeper path and decode JSON.

    JSON ``null`` is returned as ``None``; callers that disallow null must raise.
    """
    relative = _require_relative_path(path)
    url = f"{SLEEPER_BASE}{relative}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise SleeperUpstreamError(
            f"Sleeper HTTP {exc.code} for {relative}",
            status_code=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError) or (
            isinstance(reason, OSError) and getattr(reason, "errno", None) in {110, 60}
        ):
            raise SleeperUpstreamError(
                f"Sleeper timeout for {relative}",
                status_code=None,
            ) from exc
        raise SleeperUpstreamError(
            f"Sleeper URL error for {relative}: {exc.reason}",
            status_code=None,
        ) from exc
    except TimeoutError as exc:
        raise SleeperUpstreamError(
            f"Sleeper timeout for {relative}",
            status_code=None,
        ) from exc
    except OSError as exc:
        raise SleeperUpstreamError(
            f"Sleeper network error for {relative}: {exc}",
            status_code=None,
        ) from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SleeperUpstreamError(
            f"Sleeper response decode failed for {relative}",
            status_code=None,
        ) from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SleeperUpstreamError(
            f"Sleeper invalid JSON for {relative}",
            status_code=None,
        ) from exc
    except TypeError as exc:
        raise SleeperUpstreamError(
            f"Sleeper type error decoding {relative}",
            status_code=None,
        ) from exc


def _expect_dict(payload: Any, path: str) -> dict:
    if not isinstance(payload, dict):
        raise SleeperUpstreamError(
            f"Sleeper expected object for {path}, got {type(payload).__name__}",
            status_code=None,
        )
    return payload


def _expect_list_of_dicts(payload: Any, path: str) -> list[dict]:
    if not isinstance(payload, list):
        raise SleeperUpstreamError(
            f"Sleeper expected list for {path}, got {type(payload).__name__}",
            status_code=None,
        )
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise SleeperUpstreamError(
                f"Sleeper expected list of objects for {path} (index {index})",
                status_code=None,
            )
    return payload


def fetch_nfl_state() -> dict:
    path = "/state/nfl"
    return _expect_dict(sleeper_get(path), path)


def fetch_user(username: str) -> dict | None:
    encoded = urllib.parse.quote(username, safe="")
    path = f"/user/{encoded}"
    try:
        payload = sleeper_get(path)
    except SleeperUpstreamError as exc:
        if exc.status_code == 404:
            return None
        raise
    if payload is None:
        return None
    return _expect_dict(payload, path)


def fetch_user_leagues(user_id: str, season: str | int) -> list[dict]:
    path = f"/user/{urllib.parse.quote(str(user_id), safe='')}/leagues/nfl/{season}"
    return _expect_list_of_dicts(sleeper_get(path), path)


def fetch_league(league_id: str) -> dict | None:
    path = f"/league/{urllib.parse.quote(str(league_id), safe='')}"
    try:
        payload = sleeper_get(path)
    except SleeperUpstreamError as exc:
        if exc.status_code == 404:
            return None
        raise
    if payload is None:
        return None
    return _expect_dict(payload, path)


def fetch_rosters(league_id: str) -> list[dict]:
    path = f"/league/{urllib.parse.quote(str(league_id), safe='')}/rosters"
    return _expect_list_of_dicts(sleeper_get(path), path)


def fetch_users(league_id: str) -> list[dict]:
    path = f"/league/{urllib.parse.quote(str(league_id), safe='')}/users"
    return _expect_list_of_dicts(sleeper_get(path), path)


def fetch_matchups(league_id: str, week: int) -> list[dict]:
    path = f"/league/{urllib.parse.quote(str(league_id), safe='')}/matchups/{int(week)}"
    return _expect_list_of_dicts(sleeper_get(path), path)


def fetch_transactions(league_id: str, week: int) -> list[dict]:
    path = f"/league/{urllib.parse.quote(str(league_id), safe='')}/transactions/{int(week)}"
    return _expect_list_of_dicts(sleeper_get(path), path)


def fetch_traded_picks(league_id: str) -> list[dict]:
    path = f"/league/{urllib.parse.quote(str(league_id), safe='')}/traded_picks"
    return _expect_list_of_dicts(sleeper_get(path), path)


def _matchup_week_end(state: dict) -> int:
    raw = state.get("display_week")
    if raw is None:
        raw = state.get("week")
    if raw is None:
        raw = 1
    try:
        week = int(raw)
    except (TypeError, ValueError) as exc:
        raise SleeperUpstreamError(
            f"Sleeper state week is not an integer: {raw!r}",
            status_code=None,
        ) from exc
    return max(1, min(18, week))


def fetch_league_snapshot(
    league_id: str,
    *,
    state: dict | None = None,
) -> dict:
    nfl_state = state if state is not None else fetch_nfl_state()
    if not isinstance(nfl_state, dict):
        raise SleeperUpstreamError(
            "Sleeper snapshot requires state object",
            status_code=None,
        )

    league = fetch_league(league_id)
    if league is None:
        raise SleeperUpstreamError(
            f"Sleeper league not found for snapshot: {league_id}",
            status_code=404,
        )

    users = fetch_users(league_id)
    rosters = fetch_rosters(league_id)
    traded_picks = fetch_traded_picks(league_id)

    matchup_end = _matchup_week_end(nfl_state)
    matchups_by_week: dict[int, list[dict]] = {}
    for week in range(1, matchup_end + 1):
        matchups_by_week[week] = fetch_matchups(league_id, week)

    transactions_by_week: dict[int, list[dict]] = {}
    for week in range(0, 19):
        transactions_by_week[week] = fetch_transactions(league_id, week)

    return {
        "league": league,
        "users": users,
        "rosters": rosters,
        "traded_picks": traded_picks,
        "matchups_by_week": matchups_by_week,
        "transactions_by_week": transactions_by_week,
        "state": nfl_state,
    }


def _players_paths(cache_dir: Path) -> tuple[Path, Path]:
    return cache_dir / _PLAYERS_CACHE_NAME, cache_dir / _PLAYERS_META_NAME


def _read_players_cache(cache_dir: Path) -> dict[str, dict] | None:
    data_path, meta_path = _players_paths(cache_dir)
    if not data_path.is_file() or not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        fetched_raw = meta.get("fetched_at")
        if not isinstance(fetched_raw, str):
            return None
        fetched_at = datetime.fromisoformat(fetched_raw)
        if fetched_at.tzinfo is None:
            return None
        age = (_utc_now() - fetched_at.astimezone(UTC)).total_seconds()
        if age < 0 or age >= TTL:
            return None
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            return None
    return payload


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_players_cache(cache_dir: Path, players: dict[str, dict]) -> None:
    data_path, meta_path = _players_paths(cache_dir)
    fetched_at = _utc_now().astimezone(UTC).isoformat()
    data_text = json.dumps(players, separators=(",", ":"), ensure_ascii=False)
    meta_text = json.dumps({"fetched_at": fetched_at}, separators=(",", ":"))
    # Data first, then metadata — never leave a partial main file.
    _atomic_write_text(data_path, data_text)
    _atomic_write_text(meta_path, meta_text)


def get_players_nfl(
    *,
    force_refresh: bool = False,
    cache_dir: Path | None = None,
) -> dict[str, dict]:
    root = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    if not force_refresh:
        cached = _read_players_cache(root)
        if cached is not None:
            return cached

    path = "/players/nfl"
    payload = sleeper_get(path, timeout=_PLAYERS_TIMEOUT)
    if not isinstance(payload, dict):
        raise SleeperUpstreamError(
            f"Sleeper expected object for {path}, got {type(payload).__name__}",
            status_code=None,
        )
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise SleeperUpstreamError(
                f"Sleeper players dump has non-dict entry at {key!r}",
                status_code=None,
            )

    players = payload
    _write_players_cache(root, players)
    return players
