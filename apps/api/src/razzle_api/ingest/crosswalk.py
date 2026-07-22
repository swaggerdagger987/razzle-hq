"""Canonical player identity crosswalk: spine seed + DynastyProcess + Sleeper.

Three layers, kept separate so each is testable on its own:
- fetch_*: network only, no DB.
- build_*: pure row transforms, no I/O.
- upsert_*: DB only, no network.

``sync`` loads the spine, fetches overlays, builds, and upserts. It does not
commit or write ``source_syncs`` — the registry handles stamps.

Each sync is an authoritative recomputation from spine + current exact sources.
Durable T0 withholding beats prior-row retention: contested external IDs and
merge_name are written as the final computed values (including NULL).
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from razzle_api.ingest import sleeper as sleeper_mod
from razzle_api.ingest.report import SourceStamp, SyncReport

DP_PLAYERIDS_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
)
USER_AGENT = "razzle-sync/1.0"
TIMEOUT_SECONDS = 120

EXTERNAL_FIELDS = (
    "sleeper_id",
    "espn_id",
    "pfr_id",
    "cfb_player_id",
    "mfl_id",
    "fantasycalc_id",
)

IDENTITY_FIELDS = ("name", "position", "team")

_NULL_TOKENS = frozenset({"na", "nan", "null", "none"})

metadata = sa.MetaData()

players_table = sa.Table(
    "players",
    metadata,
    sa.Column("gsis_id", sa.Text, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("position", sa.Text, nullable=False),
    sa.Column("team", sa.Text, nullable=True),
)

player_ids_table = sa.Table(
    "player_ids",
    metadata,
    sa.Column("gsis_id", sa.Text, primary_key=True),
    sa.Column("sleeper_id", sa.Text, nullable=True),
    sa.Column("espn_id", sa.Text, nullable=True),
    sa.Column("pfr_id", sa.Text, nullable=True),
    sa.Column("cfb_player_id", sa.Text, nullable=True),
    sa.Column("mfl_id", sa.Text, nullable=True),
    sa.Column("fantasycalc_id", sa.Text, nullable=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("merge_name", sa.Text, nullable=True),
    sa.Column("position", sa.Text, nullable=True),
    sa.Column("team", sa.Text, nullable=True),
)


@dataclass(frozen=True)
class CrosswalkBuild:
    rows: tuple[dict[str, Any], ...]
    accepted_dp_rows: int
    applied_sleeper_rows: int
    skipped: tuple[str, ...]
    warnings: tuple[str, ...]
    conflicts: tuple[str, ...] = ()


def fetch_db_playerids() -> list[dict]:
    request = urllib.request.Request(DP_PLAYERIDS_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = response.read()
    text = payload.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def build_crosswalk_rows(
    players_rows: list[dict],
    dp_rows: list[dict],
    sleeper_players: dict[str, dict],
) -> CrosswalkBuild:
    if not players_rows:
        raise ValueError("players table is empty; refuse to build crosswalk")

    warnings: list[str] = []
    conflicts: list[str] = []
    skipped: list[str] = []

    rows_by_gsis = _seed_spine(players_rows)
    spine_gsis = frozenset(rows_by_gsis)

    accepted_dp = _accept_dp_overlays(dp_rows, skipped, conflicts)
    _withhold_external_collisions(accepted_dp, conflicts)
    accepted_dp_rows = _apply_dp_overlays(rows_by_gsis, spine_gsis, accepted_dp, skipped, warnings)

    # sleeper_id present after DP is authoritative; multi-claim must retain it.
    dp_owned_sleeper = {
        gsis_id for gsis_id, row in rows_by_gsis.items() if row.get("sleeper_id") is not None
    }
    applied_sleeper_rows = _apply_sleeper_enrich(
        rows_by_gsis, sleeper_players, dp_owned_sleeper, warnings
    )
    _withhold_external_collisions(rows_by_gsis, conflicts)

    missing_spine = spine_gsis - rows_by_gsis.keys()
    if missing_spine:
        raise RuntimeError(f"crosswalk lost spine gsis_id values: {sorted(missing_spine)}")

    rows = tuple(rows_by_gsis[key] for key in sorted(rows_by_gsis))
    return CrosswalkBuild(
        rows=rows,
        accepted_dp_rows=accepted_dp_rows,
        applied_sleeper_rows=applied_sleeper_rows,
        skipped=_dedupe_sorted(skipped),
        warnings=_dedupe_sorted(warnings),
        conflicts=_dedupe_sorted(conflicts),
    )


def upsert_player_ids(session: Session, rows: list[dict]) -> int:
    """Write authoritative final rows in two phases inside the caller's transaction.

    Phase one pre-clears all external fields + merge_name on every incoming
    gsis_id and evicts any stored holder of an external value claimed non-NULL
    by a final row (even holders outside the incoming set), so a unique external
    ID can move between rows regardless of write order. Phase two writes the
    final values. Nothing commits here; if phase two raises, the caller's
    rollback also undoes the pre-clear.
    """
    if not rows:
        return 0
    _preclear_incoming_rows(session, rows)
    _preclear_claimed_external_values(session, rows)
    for chunk in _chunks(rows):
        statement = sqlite_insert(player_ids_table)
        statement = statement.on_conflict_do_update(
            index_elements=["gsis_id"],
            set_={
                "name": statement.excluded.name,
                "position": statement.excluded.position,
                "team": statement.excluded.team,
                "sleeper_id": statement.excluded.sleeper_id,
                "espn_id": statement.excluded.espn_id,
                "pfr_id": statement.excluded.pfr_id,
                "cfb_player_id": statement.excluded.cfb_player_id,
                "mfl_id": statement.excluded.mfl_id,
                "fantasycalc_id": statement.excluded.fantasycalc_id,
                "merge_name": statement.excluded.merge_name,
            },
        )
        session.execute(statement, chunk)
    return len(rows)


def _preclear_incoming_rows(session: Session, rows: list[dict]) -> None:
    """Null out externals + merge_name on every incoming gsis_id before final writes."""
    cleared = dict.fromkeys((*EXTERNAL_FIELDS, "merge_name"))
    gsis_ids = [row["gsis_id"] for row in rows]
    for chunk in _chunks(gsis_ids):
        session.execute(
            sa.update(player_ids_table)
            .where(player_ids_table.c.gsis_id.in_(chunk))
            .values(**cleared)
        )


def _preclear_claimed_external_values(session: Session, rows: list[dict]) -> None:
    """Evict stored holders of any external value claimed non-NULL by a final row.

    Old holders may not be in the incoming set; only the contested field is
    cleared, so their unrelated mappings survive.
    """
    for field in EXTERNAL_FIELDS:
        claimed = sorted({row[field] for row in rows if row.get(field) is not None})
        if not claimed:
            continue
        column = player_ids_table.c[field]
        for chunk in _chunks(claimed):
            session.execute(
                sa.update(player_ids_table).where(column.in_(chunk)).values({field: None})
            )


def sync(session: Session, seasons: list[int] | None = None) -> SyncReport:
    del seasons  # crosswalk is global; seasons are ignored
    run_utc = datetime.now(UTC)

    players_rows = [
        dict(row)
        for row in session.execute(
            sa.select(
                players_table.c.gsis_id,
                players_table.c.name,
                players_table.c.position,
                players_table.c.team,
            )
        ).mappings()
    ]
    if not players_rows:
        raise ValueError("players table is empty; refuse to build crosswalk")

    dp_rows = fetch_db_playerids()
    sleeper_players = sleeper_mod.get_players_nfl()

    warnings: list[str] = []
    sleeper_fetched_at = _sleeper_cache_fetched_at()
    if sleeper_fetched_at is None:
        sleeper_fetched_at = run_utc
        warnings.append("sleeper_players cache metadata unavailable; using run UTC")

    build = build_crosswalk_rows(players_rows, dp_rows, sleeper_players)
    upserted_count = upsert_player_ids(session, list(build.rows))

    report_warnings = _dedupe_sorted(warnings + list(build.warnings) + list(build.conflicts))
    return SyncReport(
        adapter="crosswalk",
        stamps=(
            SourceStamp(
                "dynastyprocess_playerids",
                None,
                build.accepted_dp_rows,
                run_utc,
            ),
            SourceStamp(
                "sleeper_players",
                None,
                build.applied_sleeper_rows,
                sleeper_fetched_at,
            ),
        ),
        upserted={"player_ids": upserted_count},
        skipped=build.skipped,
        warnings=report_warnings,
    )


def _dedupe_sorted(items: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(items)))


def _normalize_identity(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in _NULL_TOKENS:
        return None
    return text


def _blank_row(
    *,
    gsis_id: str,
    name: str,
    position: str | None,
    team: str | None,
) -> dict[str, Any]:
    return {
        "gsis_id": gsis_id,
        "sleeper_id": None,
        "espn_id": None,
        "pfr_id": None,
        "cfb_player_id": None,
        "mfl_id": None,
        "fantasycalc_id": None,
        "name": name,
        "merge_name": None,
        "position": position,
        "team": team,
    }


def _seed_spine(players_rows: list[dict]) -> dict[str, dict[str, Any]]:
    rows_by_gsis: dict[str, dict[str, Any]] = {}
    for player in players_rows:
        gsis_id = _normalize_identity(player.get("gsis_id"))
        name = _normalize_identity(player.get("name"))
        if not gsis_id or not name:
            raise ValueError(f"canonical players row missing gsis_id/name: {player!r}")
        rows_by_gsis[gsis_id] = _blank_row(
            gsis_id=gsis_id,
            name=name,
            position=_normalize_identity(player.get("position")),
            team=_normalize_identity(player.get("team")),
        )
    return rows_by_gsis


def _dp_payload(row: dict) -> dict[str, Any] | None:
    gsis_id = _normalize_identity(row.get("gsis_id"))
    if not gsis_id:
        return None
    return {
        "gsis_id": gsis_id,
        "sleeper_id": _normalize_identity(row.get("sleeper_id")),
        "espn_id": _normalize_identity(row.get("espn_id")),
        "pfr_id": _normalize_identity(row.get("pfr_id")),
        "cfb_player_id": _normalize_identity(row.get("cfbref_id")),
        "mfl_id": _normalize_identity(row.get("mfl_id")),
        "fantasycalc_id": None,
        "name": _normalize_identity(row.get("name")),
        "merge_name": _normalize_identity(row.get("merge_name")),
        "position": _normalize_identity(row.get("position")),
        "team": _normalize_identity(row.get("team")),
    }


def _accept_dp_overlays(
    dp_rows: list[dict],
    skipped: list[str],
    conflicts: list[str],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_gsis = 0
    for row in dp_rows:
        payload = _dp_payload(row)
        if payload is None:
            missing_gsis += 1
            continue
        grouped[payload["gsis_id"]].append(payload)
    if missing_gsis:
        skipped.append(f"dp_missing_gsis:{missing_gsis}")

    accepted: dict[str, dict[str, Any]] = {}
    for gsis_id, payloads in grouped.items():
        unique = {tuple(sorted(payload.items())) for payload in payloads}
        if len(unique) > 1:
            conflicts.append(f"dp_duplicate_conflict:gsis_id={gsis_id}")
            skipped.append(f"dp_duplicate_conflict:gsis_id={gsis_id}")
            continue
        accepted[gsis_id] = dict(payloads[0])
    return accepted


def _apply_dp_overlays(
    rows_by_gsis: dict[str, dict[str, Any]],
    spine_gsis: frozenset[str],
    accepted_dp: dict[str, dict[str, Any]],
    skipped: list[str],
    warnings: list[str],
) -> int:
    accepted_dp_rows = 0
    for gsis_id, payload in sorted(accepted_dp.items()):
        if gsis_id in spine_gsis:
            row = rows_by_gsis[gsis_id]
            drift = [
                field
                for field in IDENTITY_FIELDS
                if payload.get(field) is not None and payload.get(field) != row.get(field)
            ]
            if drift:
                warnings.append(f"dp_identity_drift:gsis_id={gsis_id} fields={','.join(drift)}")
            for field in EXTERNAL_FIELDS:
                row[field] = payload.get(field)
            row["merge_name"] = payload.get("merge_name")
            accepted_dp_rows += 1
            continue

        dp_name = payload.get("name")
        if not dp_name:
            skipped.append(f"dp_nameless:gsis_id={gsis_id}")
            continue
        rows_by_gsis[gsis_id] = {
            "gsis_id": gsis_id,
            "sleeper_id": payload.get("sleeper_id"),
            "espn_id": payload.get("espn_id"),
            "pfr_id": payload.get("pfr_id"),
            "cfb_player_id": payload.get("cfb_player_id"),
            "mfl_id": payload.get("mfl_id"),
            "fantasycalc_id": payload.get("fantasycalc_id"),
            "name": dp_name,
            "merge_name": payload.get("merge_name"),
            "position": payload.get("position"),
            "team": payload.get("team"),
        }
        accepted_dp_rows += 1
    return accepted_dp_rows


def _withhold_external_collisions(
    rows_by_gsis: dict[str, dict[str, Any]],
    conflicts: list[str],
) -> None:
    for field in EXTERNAL_FIELDS:
        claims: dict[str, list[str]] = defaultdict(list)
        for gsis_id, row in rows_by_gsis.items():
            value = row.get(field)
            if value is not None:
                claims[str(value)].append(gsis_id)
        for value, claimants in claims.items():
            if len(claimants) < 2:
                continue
            claimants_sorted = sorted(claimants)
            conflicts.append(
                f"external_collision:field={field} value={value} gsis={','.join(claimants_sorted)}"
            )
            for gsis_id in claimants_sorted:
                rows_by_gsis[gsis_id][field] = None


def _index_sleeper_by_gsis(
    sleeper_players: dict[str, dict],
) -> dict[str, list[tuple[str, dict]]]:
    by_gsis: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for key, player in sleeper_players.items():
        if not isinstance(player, dict):
            continue
        sleeper_pid = _normalize_identity(player.get("player_id")) or _normalize_identity(key)
        if not sleeper_pid:
            continue
        gsis_id = _normalize_identity(player.get("gsis_id"))
        if gsis_id is None:
            continue
        by_gsis[gsis_id].append((sleeper_pid, player))
    return by_gsis


def _null_fill_espn(row: dict[str, Any], player: dict) -> bool:
    espn_id = _normalize_identity(player.get("espn_id"))
    if row["espn_id"] is None and espn_id is not None:
        row["espn_id"] = espn_id
        return True
    return False


def _apply_sleeper_multi_claim(
    row: dict[str, Any],
    entries: list[tuple[str, dict]],
    *,
    dp_owned: bool,
    warnings: list[str],
    applied_keys: set[str],
) -> None:
    """Multi-claim: retain DP sleeper_id; never invent one from ambiguous Sleeper fills."""
    gsis_id = row["gsis_id"]
    warnings.append(f"sleeper_multi_claim:gsis_id={gsis_id}")
    if not dp_owned:
        # No authoritative DP sleeper_id — leave NULL (do not pick among claimants).
        row["sleeper_id"] = None

    espn_values = {
        value
        for _pid, player in entries
        if (value := _normalize_identity(player.get("espn_id"))) is not None
    }
    if len(espn_values) == 1 and row["espn_id"] is None:
        row["espn_id"] = next(iter(espn_values))
        # One fill from agreeing claimants counts once, not once per claimant.
        applied_keys.add(sorted(pid for pid, _player in entries)[0])


def _apply_sleeper_unique_claim(
    row: dict[str, Any],
    sleeper_pid: str,
    player: dict,
    applied_keys: set[str],
) -> None:
    filled = False
    if row["sleeper_id"] is None:
        row["sleeper_id"] = sleeper_pid
        filled = True
    if _null_fill_espn(row, player):
        filled = True
    if filled:
        applied_keys.add(sleeper_pid)


def _apply_sleeper_key_joins(
    rows_by_gsis: dict[str, dict[str, Any]],
    sleeper_players: dict[str, dict],
    applied_keys: set[str],
) -> None:
    for row in rows_by_gsis.values():
        sleeper_id = row.get("sleeper_id")
        if sleeper_id is None:
            continue
        player = sleeper_players.get(str(sleeper_id))
        if not isinstance(player, dict):
            continue
        if _null_fill_espn(row, player):
            applied_keys.add(str(sleeper_id))


def _apply_sleeper_enrich(
    rows_by_gsis: dict[str, dict[str, Any]],
    sleeper_players: dict[str, dict],
    dp_owned_sleeper: set[str],
    warnings: list[str],
) -> int:
    applied_keys: set[str] = set()
    by_gsis = _index_sleeper_by_gsis(sleeper_players)

    for gsis_id, entries in by_gsis.items():
        row = rows_by_gsis.get(gsis_id)
        if row is None:
            continue
        if len(entries) > 1:
            _apply_sleeper_multi_claim(
                row,
                entries,
                dp_owned=gsis_id in dp_owned_sleeper,
                warnings=warnings,
                applied_keys=applied_keys,
            )
            continue
        sleeper_pid, player = entries[0]
        _apply_sleeper_unique_claim(row, sleeper_pid, player, applied_keys)

    _apply_sleeper_key_joins(rows_by_gsis, sleeper_players, applied_keys)
    return len(applied_keys)


def _sleeper_cache_fetched_at() -> datetime | None:
    """Read aware-UTC ``fetched_at`` from the K-03a cache metadata file."""
    try:
        cache_dir = sleeper_mod._default_cache_dir()
        _data_path, meta_path = sleeper_mod._players_paths(cache_dir)
        if not meta_path.is_file():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        fetched_raw = meta.get("fetched_at")
        if not isinstance(fetched_raw, str):
            return None
        fetched_at = datetime.fromisoformat(fetched_raw)
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            return None
        return fetched_at.astimezone(UTC)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return None


def _chunks[T](items: list[T], size: int = 500) -> list[list[T]]:
    return [items[start : start + size] for start in range(0, len(items), size)]
