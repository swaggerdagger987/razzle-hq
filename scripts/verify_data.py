"""Stage 0 G6 harness: bidirectional read-only replay of nflverse → DB.

Run from repo root:
    uv run python scripts/verify_data.py --sample 25 --seed 20260722
    uv run python scripts/verify_data.py --offline --players-csv PATH --week-csv 2025=PATH
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from razzle_api.config import get_settings
from razzle_api.ingest.nflverse import (
    PLAYERS_URL,
    STAT_COLUMNS,
    WEEK_STATS_URL,
    fetch_players,
    fetch_week_stats,
    map_player_row,
    map_week_row,
    player_week_stats_table,
    players_table,
)

KNOWN_UNMAPPED_FIELDS = (
    "return_yd",
    "return_td",
    "pat_made",
    "pat_missed",
    "fg_made",
    "fg_missed",
)
PLAYER_COMPARE_FIELDS = ("gsis_id", "name", "position", "team")
REQUIRED_TABLES = ("players", "player_week_stats")
FRESHNESS_COLUMNS = ("source", "season", "rows", "fetched_at")
SOURCE_PLAYERS = "nflverse_players"
SOURCE_WEEK_STATS = "nflverse_week_stats"
DEFAULT_SAMPLE = 25
DEFAULT_SEED = 20260722
DEFAULT_MAX_AGE_HOURS = 36.0
FLOAT_ABS_TOL = 1e-9


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str = ""
    details: list[str] = field(default_factory=list)
    sample_keys: list[Any] = field(default_factory=list)
    db_to_source_keys: list[Any] = field(default_factory=list)
    source_to_db_keys: list[Any] = field(default_factory=list)
    db_to_source_ok: int = 0
    db_to_source_total: int = 0
    source_to_db_ok: int = 0
    source_to_db_total: int = 0
    mismatch_count: int = 0
    warnings: list[str] = field(default_factory=list)
    season: int | None = None


@dataclass
class SourceEvidence:
    name: str
    location: str
    raw_row_count: int
    mapped_row_count: int
    fetched_at: datetime
    canonical_rows_sha256: str


@dataclass
class VerificationReport:
    results: list[CheckResult]
    sources: list[SourceEvidence]
    status: CheckStatus
    known_unmapped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sample_keys: dict[str, list[Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _report_to_dict(self)


def canonical_rows_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(
        [dict(row) for row in rows],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_seed(base: int, *parts: object) -> int:
    material = ":".join(str(part) for part in (base, *parts))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def sample_sorted_keys(keys: Sequence[Any], n: int, seed: int) -> list[Any]:
    ordered = sorted(keys)
    if not ordered:
        return []
    take = min(n, len(ordered))
    return random.Random(seed).sample(ordered, take)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _serialize_key(key: Any) -> Any:
    if isinstance(key, tuple):
        return list(key)
    return key


def _report_to_dict(report: VerificationReport) -> dict[str, Any]:
    return {
        "status": report.status.value,
        "known_unmapped": list(report.known_unmapped),
        "warnings": list(report.warnings),
        "sample_keys": {
            name: [_serialize_key(key) for key in keys]
            for name, keys in report.sample_keys.items()
        },
        "sources": [
            {
                "name": source.name,
                "location": source.location,
                "raw_row_count": source.raw_row_count,
                "mapped_row_count": source.mapped_row_count,
                "fetched_at": _ensure_utc(source.fetched_at).isoformat(),
                "canonical_rows_sha256": source.canonical_rows_sha256,
            }
            for source in report.sources
        ],
        "results": [
            {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "details": list(result.details),
                "sample_keys": [_serialize_key(key) for key in result.sample_keys],
                "db_to_source_keys": [_serialize_key(key) for key in result.db_to_source_keys],
                "source_to_db_keys": [_serialize_key(key) for key in result.source_to_db_keys],
                "db_to_source_ok": result.db_to_source_ok,
                "db_to_source_total": result.db_to_source_total,
                "source_to_db_ok": result.source_to_db_ok,
                "source_to_db_total": result.source_to_db_total,
                "mismatch_count": result.mismatch_count,
                "warnings": list(result.warnings),
                "season": result.season,
            }
            for result in report.results
        ],
    }


def _promote_required(result: CheckResult, required_checks: set[str]) -> CheckResult:
    if result.name in required_checks and result.status == CheckStatus.UNAVAILABLE:
        return CheckResult(
            name=result.name,
            status=CheckStatus.FAIL,
            message=f"required but unavailable: {result.message}",
            details=list(result.details),
            sample_keys=list(result.sample_keys),
            db_to_source_keys=list(result.db_to_source_keys),
            source_to_db_keys=list(result.source_to_db_keys),
            db_to_source_ok=result.db_to_source_ok,
            db_to_source_total=result.db_to_source_total,
            source_to_db_ok=result.source_to_db_ok,
            source_to_db_total=result.source_to_db_total,
            mismatch_count=result.mismatch_count,
            warnings=list(result.warnings),
            season=result.season,
        )
    return result


def compare_identity_capability(
    sampled_gsis_ids: Sequence[str],
    identity_rows: Sequence[Mapping[str, Any]] | None,
    *,
    columns: Sequence[str] | None = None,
) -> CheckResult:
    """Pure identity probe. ``identity_rows is None`` means table absent."""
    if identity_rows is None:
        return CheckResult(
            name="identity",
            status=CheckStatus.UNAVAILABLE,
            message="player_ids table missing (lands K-01/K-03)",
        )
    if len(identity_rows) == 0:
        return CheckResult(
            name="identity",
            status=CheckStatus.UNAVAILABLE,
            message="player_ids table empty (lands K-01/K-03)",
        )

    col_set = set(columns) if columns is not None else set(identity_rows[0].keys())
    if "gsis_id" not in col_set:
        return CheckResult(
            name="identity",
            status=CheckStatus.FAIL,
            message="player_ids missing required column gsis_id",
            details=["field=gsis_id db=missing source=required"],
        )

    present = {str(row["gsis_id"]) for row in identity_rows if row.get("gsis_id") is not None}
    details: list[str] = []
    for gsis_id in sampled_gsis_ids:
        if gsis_id not in present:
            details.append(f"key={gsis_id} field=gsis_id db=missing source={gsis_id}")
    if details:
        return CheckResult(
            name="identity",
            status=CheckStatus.FAIL,
            message=f"identity mismatches={len(details)}",
            details=details,
            sample_keys=list(sampled_gsis_ids),
            mismatch_count=len(details),
        )
    return CheckResult(
        name="identity",
        status=CheckStatus.PASS,
        message=f"identity matches={len(sampled_gsis_ids)}",
        sample_keys=list(sampled_gsis_ids),
    )


def compare_freshness_capability(  # noqa: PLR0913
    sync_rows: Sequence[Mapping[str, Any]] | None,
    *,
    columns: Sequence[str] | None = None,
    expected_players_rows: int,
    expected_week_rows_by_season: Mapping[int, int],
    max_age_hours: float,
    now: datetime,
) -> CheckResult:
    """Pure freshness probe. ``sync_rows is None`` means table absent."""
    if sync_rows is None:
        return CheckResult(
            name="freshness",
            status=CheckStatus.UNAVAILABLE,
            message="source_syncs table missing (lands K-01)",
        )

    if columns is None and sync_rows:
        col_set = set(sync_rows[0].keys())
    else:
        col_set = set(columns or ())
    missing_cols = [name for name in FRESHNESS_COLUMNS if name not in col_set]
    if missing_cols:
        return CheckResult(
            name="freshness",
            status=CheckStatus.FAIL,
            message=f"source_syncs missing columns: {','.join(missing_cols)}",
            details=[f"field={name} db=missing source=required" for name in missing_cols],
        )

    now_utc = _ensure_utc(now)
    details: list[str] = []

    def _find(source: str, season: int | None) -> Mapping[str, Any] | None:
        for row in sync_rows:
            row_source = row.get("source")
            row_season = row.get("season")
            if row_source != source:
                continue
            if season is None and row_season is None:
                return row
            if season is not None and row_season is not None and int(row_season) == int(season):
                return row
        return None

    def _check_row(label: str, source: str, season: int | None, expected_rows: int) -> None:
        row = _find(source, season)
        if row is None:
            details.append(
                f"key={label} field=row db=missing source={source} season={season}"
            )
            return
        try:
            actual_rows = int(row["rows"])
        except (TypeError, ValueError, KeyError):
            details.append(f"key={label} field=rows db={row.get('rows')!r} source={expected_rows}")
            return
        if actual_rows != expected_rows:
            details.append(
                f"key={label} field=rows db={actual_rows} source={expected_rows}"
            )
        fetched_at = parse_datetime(row.get("fetched_at"))
        if fetched_at is None:
            details.append(
                f"key={label} field=fetched_at db={row.get('fetched_at')!r} source=parseable"
            )
            return
        if fetched_at > now_utc:
            details.append(
                f"key={label} field=fetched_at db={fetched_at.isoformat()} source=not_future"
            )
            return
        age_hours = (now_utc - fetched_at).total_seconds() / 3600.0
        if age_hours > max_age_hours:
            details.append(
                f"key={label} field=age_hours db={age_hours:.3f} source<={max_age_hours}"
            )

    _check_row(SOURCE_PLAYERS, SOURCE_PLAYERS, None, expected_players_rows)
    for season, expected in sorted(expected_week_rows_by_season.items()):
        label = f"{SOURCE_WEEK_STATS}:{season}"
        _check_row(label, SOURCE_WEEK_STATS, season, expected)

    if details:
        return CheckResult(
            name="freshness",
            status=CheckStatus.FAIL,
            message=f"freshness mismatches={len(details)}",
            details=details,
            mismatch_count=len(details),
        )
    return CheckResult(
        name="freshness",
        status=CheckStatus.PASS,
        message="freshness stamps current",
    )


def _load_identity_rows(session: Session) -> tuple[list[dict[str, Any]] | None, list[str] | None]:
    bind = session.get_bind()
    inspector = sa.inspect(bind)
    if "player_ids" not in inspector.get_table_names():
        return None, None
    columns = [column["name"] for column in inspector.get_columns("player_ids")]
    rows = session.execute(sa.text("SELECT * FROM player_ids")).mappings().all()
    return [dict(row) for row in rows], columns


def _load_freshness_rows(session: Session) -> tuple[list[dict[str, Any]] | None, list[str] | None]:
    bind = session.get_bind()
    inspector = sa.inspect(bind)
    if "source_syncs" not in inspector.get_table_names():
        return None, None
    columns = [column["name"] for column in inspector.get_columns("source_syncs")]
    rows = session.execute(sa.text("SELECT * FROM source_syncs")).mappings().all()
    return [dict(row) for row in rows], columns


def _index_players(
    source_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str], list[str]]:
    accepted: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    rejected_keys: list[str] = []
    for row in source_rows:
        mapped = map_player_row(dict(row))
        gsis_id = (row.get("gsis_id") or "").strip()
        if mapped is None:
            if gsis_id:
                rejected_keys.append(gsis_id)
            continue
        key = mapped["gsis_id"]
        if key in accepted:
            if accepted[key] != mapped:
                errors.append(
                    f"key={key} field=duplicate db=conflict source=conflicting_payloads"
                )
            else:
                warnings.append(f"identical duplicate player key={key}")
        accepted[key] = mapped
    return accepted, warnings, errors, rejected_keys


def _index_weeks(
    source_rows: Sequence[Mapping[str, Any]],
    season: int,
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], Mapping[str, Any]],
    list[str],
    list[str],
    list[tuple[str, int]],
]:
    accepted: dict[tuple[str, int], dict[str, Any]] = {}
    raw_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    rejected_keys: list[tuple[str, int]] = []

    for row in source_rows:
        if "season" in row and row.get("season") not in (None, ""):
            try:
                row_season = int(float(str(row["season"])))
            except (TypeError, ValueError):
                errors.append(
                    f"key=season field=season db={season} source={row.get('season')!r}"
                )
                continue
            if row_season != season:
                errors.append(
                    f"key=({row.get('player_id')!r},{row.get('week')!r}) "
                    f"field=season db={season} source={row_season}"
                )
                continue

        mapped = map_week_row(dict(row))
        player_id = (row.get("player_id") or "").strip()
        week_raw = row.get("week")
        if mapped is None:
            if player_id and week_raw not in (None, ""):
                try:
                    rejected_keys.append((player_id, int(float(str(week_raw)))))
                except (TypeError, ValueError):
                    pass
            continue

        key = (mapped["player_id"], int(mapped["week"]))
        if key in accepted:
            if accepted[key] != mapped:
                errors.append(
                    f"key={key} field=duplicate db=conflict source=conflicting_payloads"
                )
            else:
                warnings.append(f"identical duplicate week key={key}")
        accepted[key] = mapped
        raw_by_key[key] = row
    return accepted, raw_by_key, warnings, errors, rejected_keys


def _load_db_players(session: Session) -> dict[str, dict[str, Any]]:
    rows = session.execute(sa.select(players_table)).mappings().all()
    return {
        row["gsis_id"]: {
            "gsis_id": row["gsis_id"],
            "name": row["name"],
            "position": row["position"],
            "team": row["team"],
        }
        for row in rows
    }


def _load_db_weeks(session: Session, season: int) -> dict[tuple[str, int], dict[str, Any]]:
    rows = session.execute(
        sa.select(player_week_stats_table).where(player_week_stats_table.c.season == season)
    ).mappings().all()
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["player_id"], int(row["week"]))
        out[key] = {
            "player_id": row["player_id"],
            "week": int(row["week"]),
            "season": int(row["season"]),
            **{column: float(row[column]) for column in STAT_COLUMNS},
        }
    return out


def _compare_player_fields(
    key: str,
    db_row: Mapping[str, Any] | None,
    source_row: Mapping[str, Any] | None,
) -> list[str]:
    details: list[str] = []
    if db_row is None:
        details.append(f"key={key} field=row db=missing source=present")
        return details
    if source_row is None:
        details.append(f"key={key} field=row db=present source=missing")
        return details
    for field_name in PLAYER_COMPARE_FIELDS:
        db_val = db_row.get(field_name)
        source_val = source_row.get(field_name)
        if db_val != source_val:
            details.append(
                f"key={key} field={field_name} db={db_val!r} source={source_val!r}"
            )
    return details


def _compare_week_fields(
    key: tuple[str, int],
    db_row: Mapping[str, Any] | None,
    source_row: Mapping[str, Any] | None,
    season: int,
) -> list[str]:
    details: list[str] = []
    if db_row is None:
        details.append(f"key={key} field=row db=missing source=present")
        return details
    if source_row is None:
        details.append(f"key={key} field=row db=present source=missing")
        return details
    if db_row.get("player_id") != source_row.get("player_id"):
        details.append(
            f"key={key} field=player_id "
            f"db={db_row.get('player_id')!r} source={source_row.get('player_id')!r}"
        )
    if int(db_row.get("week")) != int(source_row.get("week")):
        details.append(
            f"key={key} field=week db={db_row.get('week')!r} source={source_row.get('week')!r}"
        )
    if int(db_row.get("season", season)) != season:
        details.append(
            f"key={key} field=season db={db_row.get('season')!r} source={season}"
        )
    for column in STAT_COLUMNS:
        db_val = float(db_row[column])
        source_val = float(source_row[column])
        if not math.isclose(db_val, source_val, rel_tol=0.0, abs_tol=FLOAT_ABS_TOL):
            details.append(
                f"key={key} field={column} db={db_val!r} source={source_val!r}"
            )
    return details


def _verify_players(
    *,
    db_players: Mapping[str, Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
    sample_size: int,
    seed: int,
) -> CheckResult:
    accepted, warnings, errors, rejected_keys = _index_players(source_rows)
    details = list(errors)
    db_keys = list(db_players.keys())
    source_keys = list(accepted.keys())

    if errors:
        return CheckResult(
            name="players",
            status=CheckStatus.FAIL,
            message=f"player source index errors={len(errors)}",
            details=details,
            warnings=warnings,
        )

    undersized = (
        not db_keys
        or not source_keys
        or len(db_keys) < sample_size
        or len(source_keys) < sample_size
    )
    if undersized:
        return CheckResult(
            name="players",
            status=CheckStatus.FAIL,
            message=(
                f"undersized/empty players db={len(db_keys)} "
                f"source={len(source_keys)} sample_size={sample_size}"
            ),
            details=[
                f"db_count={len(db_keys)} source_accepted={len(source_keys)} "
                f"sample_size={sample_size}"
            ],
            warnings=warnings,
        )

    db_sample = sample_sorted_keys(
        db_keys, sample_size, derive_seed(seed, "players", "db_to_source")
    )
    source_sample = sample_sorted_keys(
        source_keys, sample_size, derive_seed(seed, "players", "source_to_db")
    )

    for key in db_sample:
        details.extend(_compare_player_fields(key, db_players.get(key), accepted.get(key)))
    for key in source_sample:
        details.extend(_compare_player_fields(key, db_players.get(key), accepted.get(key)))

    if rejected_keys:
        neg_sample = sample_sorted_keys(
            sorted(set(rejected_keys)),
            sample_size,
            derive_seed(seed, "players", "negative_filter"),
        )
        for key in neg_sample:
            if key in db_players:
                details.append(f"key={key} field=filter_leak db=present source=rejected")
    else:
        warnings.append("no negative player filter rows available for audit")

    mismatch_count = len(details)
    db_mismatches = [
        key
        for key in db_sample
        if _compare_player_fields(key, db_players.get(key), accepted.get(key))
    ]
    source_mismatches = [
        key
        for key in source_sample
        if _compare_player_fields(key, db_players.get(key), accepted.get(key))
    ]
    db_ok = sample_size - len(db_mismatches)
    source_ok = sample_size - len(source_mismatches)
    status = CheckStatus.PASS if mismatch_count == 0 else CheckStatus.FAIL
    return CheckResult(
        name="players",
        status=status,
        message=(
            f"db->source={db_ok}/{sample_size} source->db={source_ok}/{sample_size} "
            f"identity_mismatches={mismatch_count}"
        ),
        details=details,
        sample_keys=[*db_sample, *source_sample],
        db_to_source_keys=db_sample,
        source_to_db_keys=source_sample,
        db_to_source_ok=db_ok,
        db_to_source_total=sample_size,
        source_to_db_ok=source_ok,
        source_to_db_total=sample_size,
        mismatch_count=mismatch_count,
        warnings=warnings,
    )


def _verify_weeks(  # noqa: PLR0913
    *,
    season: int,
    db_weeks: Mapping[tuple[str, int], Mapping[str, Any]],
    db_players: Mapping[str, Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
    sample_size: int,
    seed: int,
) -> CheckResult:
    accepted, raw_by_key, warnings, errors, rejected_keys = _index_weeks(source_rows, season)
    details = list(errors)
    name = "player_week_stats"

    if errors:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=f"week source index errors={len(errors)}",
            details=details,
            warnings=warnings,
            season=season,
        )

    db_keys = list(db_weeks.keys())
    source_keys = list(accepted.keys())
    undersized = (
        not db_keys
        or not source_keys
        or len(db_keys) < sample_size
        or len(source_keys) < sample_size
    )
    if undersized:
        return CheckResult(
            name=name,
            status=CheckStatus.FAIL,
            message=(
                f"undersized/empty player_week_stats season={season} "
                f"db={len(db_keys)} source={len(source_keys)} sample_size={sample_size}"
            ),
            details=[
                f"season={season} db_count={len(db_keys)} "
                f"source_accepted={len(source_keys)} sample_size={sample_size}"
            ],
            warnings=warnings,
            season=season,
        )

    db_sample = sample_sorted_keys(
        db_keys, sample_size, derive_seed(seed, "weeks", season, "db_to_source")
    )
    source_sample = sample_sorted_keys(
        source_keys, sample_size, derive_seed(seed, "weeks", season, "source_to_db")
    )

    for key in db_sample:
        details.extend(_compare_week_fields(key, db_weeks.get(key), accepted.get(key), season))
    for key in source_sample:
        details.extend(_compare_week_fields(key, db_weeks.get(key), accepted.get(key), season))

    integrity_keys = list(dict.fromkeys([*db_sample, *source_sample]))
    for key in integrity_keys:
        player_id, _week = key
        player = db_players.get(player_id)
        if player is None:
            details.append(f"key={key} field=player_id db=missing source={player_id}")
            continue
        raw = raw_by_key.get(key)
        if raw is None:
            continue
        raw_position = (raw.get("position") or "").strip()
        if player.get("position") != raw_position:
            details.append(
                f"key={key} field=position db={player.get('position')!r} "
                f"source={raw_position!r}"
            )

    if rejected_keys:
        neg_sample = sample_sorted_keys(
            sorted(set(rejected_keys)),
            sample_size,
            derive_seed(seed, "weeks", season, "negative_filter"),
        )
        for key in neg_sample:
            if key in db_weeks:
                details.append(f"key={key} field=filter_leak db=present source=rejected")
    else:
        warnings.append(f"no negative week filter rows available for audit season={season}")

    mismatch_count = len(details)
    db_mismatches = [
        key
        for key in db_sample
        if _compare_week_fields(key, db_weeks.get(key), accepted.get(key), season)
    ]
    source_mismatches = [
        key
        for key in source_sample
        if _compare_week_fields(key, db_weeks.get(key), accepted.get(key), season)
    ]
    db_ok = sample_size - len(db_mismatches)
    source_ok = sample_size - len(source_mismatches)
    status = CheckStatus.PASS if mismatch_count == 0 else CheckStatus.FAIL
    return CheckResult(
        name=name,
        status=status,
        message=(
            f"season={season} db->source={db_ok}/{sample_size} "
            f"source->db={source_ok}/{sample_size} stat_mismatches={mismatch_count}"
        ),
        details=details,
        sample_keys=[*db_sample, *source_sample],
        db_to_source_keys=db_sample,
        source_to_db_keys=source_sample,
        db_to_source_ok=db_ok,
        db_to_source_total=sample_size,
        source_to_db_ok=source_ok,
        source_to_db_total=sample_size,
        mismatch_count=mismatch_count,
        warnings=warnings,
        season=season,
    )


def verify(  # noqa: PLR0913
    session: Session,
    *,
    sample_size: int,
    seed: int,
    seasons: list[int],
    player_source_rows: list[dict],
    week_source_rows_by_season: dict[int, list[dict]],
    required_checks: set[str],
    max_age_hours: float,
    fetched_at: datetime | None = None,
    source_locations: Mapping[str, str] | None = None,
) -> VerificationReport:
    """Run read-only verification against an open session and in-memory source rows."""
    if sample_size < 1:
        raise ValueError("sample_size must be >= 1")
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be > 0")

    as_of = _ensure_utc(fetched_at or _utc_now())
    locations = dict(source_locations or {})
    warnings: list[str] = []
    results: list[CheckResult] = []
    sources: list[SourceEvidence] = []
    sample_keys: dict[str, list[Any]] = {}

    player_mapped = [
        mapped
        for mapped in (map_player_row(row) for row in player_source_rows)
        if mapped
    ]
    sources.append(
        SourceEvidence(
            name="players",
            location=locations.get("players", PLAYERS_URL),
            raw_row_count=len(player_source_rows),
            mapped_row_count=len(player_mapped),
            fetched_at=as_of,
            canonical_rows_sha256=canonical_rows_sha256(player_source_rows),
        )
    )

    mapped_week_counts: dict[int, int] = {}
    for season in seasons:
        week_rows = week_source_rows_by_season.get(season, [])
        mapped_weeks = [mapped for mapped in (map_week_row(row) for row in week_rows) if mapped]
        mapped_week_counts[season] = len(mapped_weeks)
        sources.append(
            SourceEvidence(
                name=f"player_week_stats_{season}",
                location=locations.get(
                    f"week_{season}", WEEK_STATS_URL.format(season=season)
                ),
                raw_row_count=len(week_rows),
                mapped_row_count=len(mapped_weeks),
                fetched_at=as_of,
                canonical_rows_sha256=canonical_rows_sha256(week_rows),
            )
        )

    db_players = _load_db_players(session)
    players_result = _verify_players(
        db_players=db_players,
        source_rows=player_source_rows,
        sample_size=sample_size,
        seed=seed,
    )
    sample_keys["players.db_to_source"] = list(players_result.db_to_source_keys)
    sample_keys["players.source_to_db"] = list(players_result.source_to_db_keys)
    results.append(players_result)
    warnings.extend(players_result.warnings)

    for season in seasons:
        db_weeks = _load_db_weeks(session, season)
        week_result = _verify_weeks(
            season=season,
            db_weeks=db_weeks,
            db_players=db_players,
            source_rows=week_source_rows_by_season.get(season, []),
            sample_size=sample_size,
            seed=seed,
        )
        sample_keys[f"player_week_stats.{season}.db_to_source"] = list(
            week_result.db_to_source_keys
        )
        sample_keys[f"player_week_stats.{season}.source_to_db"] = list(
            week_result.source_to_db_keys
        )
        results.append(week_result)
        warnings.extend(week_result.warnings)

    identity_rows, identity_columns = _load_identity_rows(session)
    identity_sample = sample_sorted_keys(
        list(db_players.keys()),
        sample_size,
        derive_seed(seed, "identity", "players"),
    )
    identity_result = compare_identity_capability(
        identity_sample,
        identity_rows,
        columns=identity_columns,
    )
    identity_result = _promote_required(identity_result, required_checks)
    results.append(identity_result)

    freshness_rows, freshness_columns = _load_freshness_rows(session)
    freshness_result = compare_freshness_capability(
        freshness_rows,
        columns=freshness_columns,
        expected_players_rows=len(player_mapped),
        expected_week_rows_by_season=mapped_week_counts,
        max_age_hours=max_age_hours,
        now=as_of,
    )
    freshness_result = _promote_required(freshness_result, required_checks)
    results.append(freshness_result)

    results.append(
        CheckResult(
            name="cross_source",
            status=CheckStatus.UNAVAILABLE,
            message="second source not installed",
        )
    )

    known_unmapped = [
        f"{','.join(KNOWN_UNMAPPED_FIELDS)}: not source-complete (adapter zeros)"
    ]

    overall = (
        CheckStatus.FAIL
        if any(result.status == CheckStatus.FAIL for result in results)
        else CheckStatus.PASS
    )
    return VerificationReport(
        results=results,
        sources=sources,
        status=overall,
        known_unmapped=known_unmapped,
        warnings=warnings,
        sample_keys=sample_keys,
    )


def format_human_report(report: VerificationReport) -> str:
    lines: list[str] = []
    for source in report.sources:
        fetched = _ensure_utc(source.fetched_at).isoformat()
        lines.append(
            f"SOURCE {source.name} location={source.location} "
            f"raw_rows={source.raw_row_count} mapped_rows={source.mapped_row_count} "
            f"canonical_rows_sha256={source.canonical_rows_sha256} "
            f"fetched_at={fetched}"
        )

    for result in report.results:
        if result.name == "players":
            lines.append(
                f"{result.status.value} players "
                f"db->source={result.db_to_source_ok}/{result.db_to_source_total} "
                f"source->db={result.source_to_db_ok}/{result.source_to_db_total} "
                f"identity_mismatches={result.mismatch_count}"
            )
        elif result.name == "player_week_stats":
            lines.append(
                f"{result.status.value} player_week_stats season={result.season} "
                f"db->source={result.db_to_source_ok}/{result.db_to_source_total} "
                f"source->db={result.source_to_db_ok}/{result.source_to_db_total} "
                f"stat_mismatches={result.mismatch_count}"
            )
        elif result.status == CheckStatus.UNAVAILABLE:
            lines.append(f"UNAVAILABLE {result.name}: {result.message}")
        else:
            lines.append(f"{result.status.value} {result.name}: {result.message}")
        for detail in result.details:
            lines.append(f"  {detail}")
        for warning in result.warnings:
            lines.append(f"WARNING {warning}")

    for warning in report.warnings:
        if not any(warning in line for line in lines):
            lines.append(f"WARNING {warning}")

    for item in report.known_unmapped:
        lines.append(f"KNOWN_UNMAPPED {item}")

    lines.append(f"RESULT {report.status.value}")
    return "\n".join(lines)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sqlite_file_path(database_url: str) -> Path | None:
    if database_url == "sqlite:///:memory:" or database_url.startswith("sqlite:///:memory:"):
        return None
    if not database_url.startswith("sqlite:///"):
        return None
    path_part = database_url.removeprefix("sqlite:///")
    if path_part == ":memory:" or path_part.startswith(":memory:"):
        return None
    return Path(path_part)


def _create_engine(database_url: str) -> Engine:
    path = _sqlite_file_path(database_url)
    if path is not None and not path.exists():
        raise FileNotFoundError(f"database file not found: {path}")
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return sa.create_engine(database_url, connect_args=connect_args)


def _require_tables(engine: Engine) -> None:
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    if missing:
        raise RuntimeError(f"missing required tables: {', '.join(missing)}")


def list_db_seasons(session: Session) -> list[int]:
    rows = session.execute(
        sa.select(player_week_stats_table.c.season)
        .distinct()
        .order_by(player_week_stats_table.c.season)
    ).scalars().all()
    return [int(season) for season in rows]


def _parse_week_csv(values: list[str] | None) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"invalid --week-csv value (expected SEASON=PATH): {item}")
        season_text, path_text = item.split("=", 1)
        try:
            season = int(season_text)
        except ValueError as exc:
            raise ValueError(f"invalid season in --week-csv: {item}") from exc
        out[season] = Path(path_text)
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--seasons", nargs="+", type=int)
    parser.add_argument("--database-url")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--players-csv", type=Path)
    parser.add_argument("--week-csv", action="append", default=[])
    parser.add_argument(
        "--require",
        action="append",
        choices=("identity", "freshness"),
        default=[],
    )
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    parser.add_argument("--json", action="store_true")
    return parser


def _cli_arg_error(args: argparse.Namespace) -> str | None:
    if args.sample < 1:
        return "error: --sample must be an integer >= 1"
    if args.max_age_hours <= 0:
        return "error: --max-age-hours must be > 0"
    return None


def _open_verify_engine(database_url: str) -> Engine:
    engine = _create_engine(database_url)
    _require_tables(engine)
    return engine


def _offline_missing_paths(
    *,
    players_csv: Path | None,
    seasons: list[int],
    week_paths: dict[int, Path],
) -> list[str]:
    missing: list[str] = []
    if players_csv is None:
        return ["<players-csv>"]
    if not players_csv.exists():
        missing.append(str(players_csv))
    for season in seasons:
        path = week_paths.get(season)
        if path is None or not path.exists():
            missing.append(f"{season}={path}" if path else f"{season}=<missing>")
    return missing


def _load_sources(
    *,
    offline: bool,
    players_csv: Path | None,
    seasons: list[int],
    week_paths: dict[int, Path],
) -> tuple[list[dict], dict[int, list[dict]], dict[str, str]]:
    locations: dict[str, str] = {}
    if players_csv is not None:
        if not players_csv.exists():
            raise FileNotFoundError(f"players csv not found: {players_csv}")
        player_source_rows = read_csv_rows(players_csv)
        locations["players"] = str(players_csv)
    elif offline:
        raise ValueError("--offline requires --players-csv")
    else:
        player_source_rows = fetch_players()
        locations["players"] = PLAYERS_URL

    week_source_rows_by_season: dict[int, list[dict]] = {}
    for season in seasons:
        path = week_paths.get(season)
        if path is not None:
            if not path.exists():
                raise FileNotFoundError(f"week csv not found: {path}")
            week_source_rows_by_season[season] = read_csv_rows(path)
            locations[f"week_{season}"] = str(path)
        elif offline:
            raise FileNotFoundError(f"offline missing --week-csv for season {season}")
        else:
            week_source_rows_by_season[season] = fetch_week_stats(season)
            locations[f"week_{season}"] = WEEK_STATS_URL.format(season=season)
    return player_source_rows, week_source_rows_by_season, locations


def run_cli(argv: list[str] | None = None) -> int:  # noqa: PLR0911, PLR0912, PLR0915
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 2

    arg_error = _cli_arg_error(args)
    if arg_error is not None:
        print(arg_error, file=sys.stderr)
        return 2

    try:
        week_paths = _parse_week_csv(args.week_csv)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    database_url = args.database_url or get_settings().database_url
    engine: Engine | None = None
    try:
        engine = _open_verify_engine(database_url)
    except Exception as exc:  # noqa: BLE001 — operational exit 2
        print(f"error: database unavailable: {exc}", file=sys.stderr)
        return 2

    session_factory = sessionmaker(engine, expire_on_commit=False)
    try:
        with session_factory() as session:
            try:
                seasons = list(args.seasons) if args.seasons else list_db_seasons(session)
            except Exception as exc:  # noqa: BLE001
                print(f"error: failed reading seasons: {exc}", file=sys.stderr)
                return 2

            if args.offline:
                if args.players_csv is None:
                    print("error: --offline requires --players-csv", file=sys.stderr)
                    return 2
                missing = _offline_missing_paths(
                    players_csv=args.players_csv,
                    seasons=seasons,
                    week_paths=week_paths,
                )
                if missing:
                    joined = ", ".join(missing)
                    print(f"error: offline source path(s) missing: {joined}", file=sys.stderr)
                    return 2

            fetched_at = _utc_now()
            try:
                player_rows, week_rows, locations = _load_sources(
                    offline=args.offline,
                    players_csv=args.players_csv,
                    seasons=seasons,
                    week_paths=week_paths,
                )
            except Exception as exc:  # noqa: BLE001 — network/parse/I/O
                print(f"error: source load failed: {exc}", file=sys.stderr)
                return 2

            report = verify(
                session,
                sample_size=args.sample,
                seed=args.seed,
                seasons=seasons,
                player_source_rows=player_rows,
                week_source_rows_by_season=week_rows,
                required_checks=set(args.require),
                max_age_hours=args.max_age_hours,
                fetched_at=fetched_at,
                source_locations=locations,
            )
    finally:
        engine.dispose()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_human_report(report))

    return 1 if report.status == CheckStatus.FAIL else 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
