"""Persist immutable league context revisions (connect / refresh / get)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from razzle_api.core.provenance import build_meta
from razzle_api.domain.scoring import compile_league
from razzle_api.ingest import sleeper

_JSON_DUMP_KW = {"ensure_ascii": False, "separators": (",", ":")}
_PERSIST_ATTEMPTS = 3
_OWNED_ASSUMPTION = "explicitly owned leagues"
_SNAPSHOT_KEYS = (
    "league",
    "users",
    "rosters",
    "traded_picks",
    "matchups_by_week",
    "transactions_by_week",
    "state",
)

_metadata = sa.MetaData()

leagues_table = sa.Table(
    "leagues",
    _metadata,
    sa.Column("league_id", sa.Text, primary_key=True),
    sa.Column("sleeper_user_id", sa.Text, nullable=False),
    sa.Column("username", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("season", sa.Integer, nullable=False),
    sa.Column("sport", sa.Text, nullable=False),
    sa.Column("total_rosters", sa.Integer, nullable=True),
    sa.Column("created_at", sa.Text, nullable=False),
    sa.Column("updated_at", sa.Text, nullable=False),
)

context_revisions_table = sa.Table(
    "context_revisions",
    _metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("league_id", sa.Text, nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("compiled_rules_json", sa.Text, nullable=False),
    sa.Column("coverage_json", sa.Text, nullable=False),
    sa.Column("snapshot_json", sa.Text, nullable=False),
    sa.Column("sources_json", sa.Text, nullable=False),
    sa.Column("created_at", sa.Text, nullable=False),
)


class ContextNotFoundError(Exception):
    """Unknown user or missing resource."""


class ContextForbiddenError(Exception):
    """Caller does not own the requested league."""


class ContextUpstreamError(Exception):
    """Sleeper (or related) upstream failure."""


@dataclass(frozen=True)
class _LeagueRecord:
    league_id: str
    owner_user_id: str
    owner_username: str
    name: str
    season: int
    sport: str
    total_rosters: int | None


@dataclass(frozen=True)
class _RevisionBlobs:
    revision_id: str
    created_at: str
    snapshot_json: str
    compiled_rules_json: str
    coverage_json: str
    sources_json: str


@dataclass(frozen=True)
class _RevisionView:
    revision_id: str
    league_id: str
    season: int
    created_at: datetime
    snapshot: dict[str, Any]
    compiled_rules: dict[str, Any]
    coverage: dict[str, Any]
    meta: dict[str, Any]


def connect_username(session: Session, username: str) -> dict:
    """List the caller's owned leagues for the current Sleeper season. No DB writes."""
    del session  # connect never touches the database
    user, state, leagues = _fetch_owned_leagues(username)
    season = _season_int(state.get("league_season"))
    as_of = datetime.now(UTC)
    summaries = [_league_summary(league) for league in leagues]
    meta = build_meta(
        revision=None,
        sources={"name": "sleeper", "as_of": as_of},
        assumptions=(_OWNED_ASSUMPTION,),
    )
    return {
        "user": _user_identity(user),
        "season": season,
        "leagues": summaries,
        "meta": meta,
    }


def refresh_league(session: Session, sleeper_league_id: str, *, username: str) -> dict:
    """Fetch a complete snapshot, compile rules, and persist a new immutable revision."""
    user, state, leagues = _fetch_owned_leagues(username)
    owned_ids = {str(league.get("league_id")) for league in leagues}
    league_id = str(sleeper_league_id)
    if league_id not in owned_ids:
        raise ContextForbiddenError(f"league not owned: {league_id}")

    try:
        snapshot_raw = sleeper.fetch_league_snapshot(league_id, state=state)
    except sleeper.SleeperUpstreamError as exc:
        raise ContextUpstreamError(exc.message) from exc

    snapshot = _require_snapshot(snapshot_raw)
    league_payload = snapshot["league"]
    season = _season_int(league_payload.get("season"))
    compiled = compile_league(league_payload)
    compiled_rules = compiled.model_dump(mode="json")
    coverage = compiled.coverage.model_dump(mode="json")

    as_of = datetime.now(UTC)
    revision_id = uuid.uuid4().hex
    created_at = _format_utc(as_of)
    sources_list: list[dict[str, Any]] = [{"name": "sleeper", "as_of": _format_utc(as_of)}]

    snapshot_json = json.dumps(snapshot, **_JSON_DUMP_KW)
    compiled_rules_json = json.dumps(compiled_rules, **_JSON_DUMP_KW)
    coverage_json = json.dumps(coverage, **_JSON_DUMP_KW)
    sources_json = json.dumps(sources_list, **_JSON_DUMP_KW)

    owner_user_id = _require_user_id(user)
    owner_username = str(user.get("username") or username)
    name = str(league_payload.get("name") or "")
    sport = str(league_payload.get("sport") or "nfl")
    total_rosters = _optional_int(league_payload.get("total_rosters"))

    _persist_revision(
        session,
        league=_LeagueRecord(
            league_id=league_id,
            owner_user_id=owner_user_id,
            owner_username=owner_username,
            name=name,
            season=season,
            sport=sport,
            total_rosters=total_rosters,
        ),
        blobs=_RevisionBlobs(
            revision_id=revision_id,
            created_at=created_at,
            snapshot_json=snapshot_json,
            compiled_rules_json=compiled_rules_json,
            coverage_json=coverage_json,
            sources_json=sources_json,
        ),
    )

    meta = build_meta(
        revision=revision_id,
        sources=[{"name": "sleeper", "as_of": as_of}],
        coverage=coverage,
    )
    return _revision_payload(
        _RevisionView(
            revision_id=revision_id,
            league_id=league_id,
            season=season,
            created_at=as_of,
            snapshot=snapshot,
            compiled_rules=compiled_rules,
            coverage=coverage,
            meta=meta,
        )
    )


def get_revision(session: Session, revision_id: str) -> dict | None:
    """Load a stored revision offline. Returns None when unknown."""
    row = (
        session.execute(
            sa.select(
                context_revisions_table.c.id,
                context_revisions_table.c.league_id,
                context_revisions_table.c.compiled_rules_json,
                context_revisions_table.c.coverage_json,
                context_revisions_table.c.snapshot_json,
                context_revisions_table.c.sources_json,
                context_revisions_table.c.created_at,
                leagues_table.c.season,
            )
            .select_from(
                context_revisions_table.join(
                    leagues_table,
                    context_revisions_table.c.league_id == leagues_table.c.league_id,
                )
            )
            .where(context_revisions_table.c.id == revision_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    snapshot = json.loads(row["snapshot_json"])
    if not isinstance(snapshot, dict):
        snapshot = {}
    snapshot["matchups_by_week"] = _coerce_week_map(snapshot.get("matchups_by_week"))
    snapshot["transactions_by_week"] = _coerce_week_map(snapshot.get("transactions_by_week"))

    compiled_rules = json.loads(row["compiled_rules_json"])
    coverage = json.loads(row["coverage_json"])
    sources_raw = json.loads(row["sources_json"])
    sources = [_parse_source(item) for item in sources_raw]
    created_at = _parse_aware(row["created_at"])
    meta = build_meta(
        revision=row["id"],
        sources=sources,
        coverage=coverage,
    )
    return _revision_payload(
        _RevisionView(
            revision_id=row["id"],
            league_id=row["league_id"],
            season=int(row["season"]),
            created_at=created_at,
            snapshot=snapshot,
            compiled_rules=compiled_rules,
            coverage=coverage,
            meta=meta,
        )
    )


def _fetch_owned_leagues(username: str) -> tuple[dict, dict, list[dict]]:
    try:
        user = sleeper.fetch_user(username)
    except sleeper.SleeperUpstreamError as exc:
        raise ContextUpstreamError(exc.message) from exc
    if user is None:
        raise ContextNotFoundError(f"user not found: {username}")
    if not isinstance(user, dict):
        raise ContextUpstreamError("user payload is not an object")
    user_id = _require_user_id(user)

    try:
        state = sleeper.fetch_nfl_state()
    except sleeper.SleeperUpstreamError as exc:
        raise ContextUpstreamError(exc.message) from exc
    if not isinstance(state, dict):
        raise ContextUpstreamError("state payload is not an object")
    season_raw = state.get("league_season")
    # Validate season before leagues fetch so bad state fails closed.
    _season_int(season_raw)

    try:
        leagues = sleeper.fetch_user_leagues(user_id, season_raw)
    except sleeper.SleeperUpstreamError as exc:
        raise ContextUpstreamError(exc.message) from exc

    return user, state, leagues


def _persist_revision(
    session: Session,
    *,
    league: _LeagueRecord,
    blobs: _RevisionBlobs,
) -> None:
    last_error: IntegrityError | None = None
    for _ in range(_PERSIST_ATTEMPTS):
        try:
            _upsert_league(session, league=league, stamp=blobs.created_at)
            next_revision = _next_revision_number(session, league.league_id)
            session.execute(
                sa.insert(context_revisions_table).values(
                    id=blobs.revision_id,
                    league_id=league.league_id,
                    revision=next_revision,
                    compiled_rules_json=blobs.compiled_rules_json,
                    coverage_json=blobs.coverage_json,
                    snapshot_json=blobs.snapshot_json,
                    sources_json=blobs.sources_json,
                    created_at=blobs.created_at,
                )
            )
            session.commit()
            return
        except IntegrityError as exc:
            last_error = exc
            session.rollback()
    assert last_error is not None
    raise last_error


def _upsert_league(session: Session, *, league: _LeagueRecord, stamp: str) -> None:
    existing = (
        session.execute(
            sa.select(leagues_table.c.league_id, leagues_table.c.created_at).where(
                leagues_table.c.league_id == league.league_id
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        session.execute(
            sa.insert(leagues_table).values(
                league_id=league.league_id,
                sleeper_user_id=league.owner_user_id,
                username=league.owner_username,
                name=league.name,
                season=league.season,
                sport=league.sport,
                total_rosters=league.total_rosters,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        return

    session.execute(
        sa.update(leagues_table)
        .where(leagues_table.c.league_id == league.league_id)
        .values(
            sleeper_user_id=league.owner_user_id,
            username=league.owner_username,
            name=league.name,
            season=league.season,
            sport=league.sport,
            total_rosters=league.total_rosters,
            updated_at=stamp,
        )
    )


def _next_revision_number(session: Session, league_id: str) -> int:
    current = session.execute(
        sa.select(sa.func.coalesce(sa.func.max(context_revisions_table.c.revision), 0)).where(
            context_revisions_table.c.league_id == league_id
        )
    ).scalar_one()
    return int(current) + 1


def _revision_payload(view: _RevisionView) -> dict:
    snapshot = view.snapshot
    return {
        "revision_id": view.revision_id,
        "league_id": view.league_id,
        "season": view.season,
        "created_at": view.created_at,
        "league": snapshot["league"],
        "users": snapshot["users"],
        "rosters": snapshot["rosters"],
        "matchups_by_week": snapshot["matchups_by_week"],
        "transactions_by_week": snapshot["transactions_by_week"],
        "traded_picks": snapshot["traded_picks"],
        "state": snapshot["state"],
        "compiled_rules": view.compiled_rules,
        "coverage": view.coverage,
        "meta": view.meta,
    }


def _require_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ContextUpstreamError("league snapshot is not an object")
    for key in _SNAPSHOT_KEYS:
        if key not in snapshot:
            raise ContextUpstreamError(f"league snapshot missing {key}")
    league = snapshot["league"]
    if not isinstance(league, dict):
        raise ContextUpstreamError("league snapshot has wrong league payload")
    for key in ("users", "rosters", "traded_picks"):
        if not isinstance(snapshot[key], list):
            raise ContextUpstreamError(f"league snapshot {key} is not a list")
    for key in ("matchups_by_week", "transactions_by_week", "state"):
        if not isinstance(snapshot[key], dict):
            raise ContextUpstreamError(f"league snapshot {key} is not an object")
    return snapshot


def _league_summary(league: dict[str, Any]) -> dict[str, Any]:
    return {
        "league_id": str(league.get("league_id") or ""),
        "name": str(league.get("name") or ""),
        "season": _season_int(league.get("season")),
        "sport": str(league.get("sport") or "nfl"),
        "total_rosters": _optional_int(league.get("total_rosters")),
    }


def _user_identity(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": _require_user_id(user),
        "username": str(user.get("username") or ""),
        "display_name": user.get("display_name"),
        "avatar": user.get("avatar"),
    }


def _require_user_id(user: dict[str, Any]) -> str:
    user_id = user.get("user_id")
    if not isinstance(user_id, str) or user_id == "":
        raise ContextUpstreamError(f"user_id is missing or not a string: {user_id!r}")
    return user_id


def _season_int(raw: Any) -> int:
    if isinstance(raw, bool) or raw is None:
        raise ContextUpstreamError(f"season is not an integer: {raw!r}")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ContextUpstreamError(f"season is not an integer: {raw!r}") from exc


def _optional_int(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise ContextUpstreamError(f"total_rosters is not an integer: {raw!r}")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ContextUpstreamError(f"total_rosters is not an integer: {raw!r}") from exc


def _coerce_week_map(raw: Any) -> dict[int, list]:
    if not isinstance(raw, dict):
        return {}
    coerced: dict[int, list] = {}
    for key, value in raw.items():
        coerced[int(key)] = value if isinstance(value, list) else []
    return coerced


def _parse_source(item: Any) -> dict[str, Any]:
    payload = dict(item)
    as_of = payload.get("as_of")
    if isinstance(as_of, str):
        payload["as_of"] = _parse_aware(as_of)
    return payload


def _parse_aware(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
