"""Canonical player identity crosswalk: spine seed + DynastyProcess + Sleeper.

Three layers, kept separate so each is testable on its own:
- fetch_*: network only, no DB.
- build_*: pure row transforms, no I/O.
- upsert_*: DB only, no network.

``sync`` loads the spine, fetches overlays, builds, and upserts. It does not
commit or write ``source_syncs`` — the registry handles stamps.
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

from razzle_api.ingest.report import SourceStamp, SyncReport
from razzle_api.ingest.sleeper import _players_paths, get_players_nfl

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

    # Layer 0 — seed every canonical spine row.
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
    spine_gsis = frozenset(rows_by_gsis)

    # Layer 1 — DynastyProcess exact-gsis overlay.
    accepted_dp = _accept_dp_overlays(dp_rows, skipped, conflicts)
    _withhold_external_collisions(accepted_dp, conflicts)

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

        # DP-only resolved gsis: insert with DP name; nameless skips.
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

    # Layer 2 — Sleeper exact-key enrich (NULL-fill only).
    applied_sleeper_rows = _apply_sleeper_enrich(rows_by_gsis, sleeper_players, warnings)
    _withhold_external_collisions(rows_by_gsis, conflicts)

    # Final invariant: every spine gsis_id is present.
    missing_spine = spine_gsis - rows_by_gsis.keys()
    if missing_spine:
        raise RuntimeError(f"crosswalk lost spine gsis_id values: {sorted(missing_spine)}")

    rows = tuple(rows_by_gsis[key] for key in sorted(rows_by_gsis))
    return CrosswalkBuild(
        rows=rows,
        accepted_dp_rows=accepted_dp_rows,
        applied_sleeper_rows=applied_sleeper_rows,
        skipped=tuple(skipped),
        warnings=tuple(warnings),
        conflicts=tuple(conflicts),
    )


def upsert_player_ids(session: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    for chunk in _chunks(rows):
        statement = sqlite_insert(player_ids_table)
        statement = statement.on_conflict_do_update(
            index_elements=["gsis_id"],
            set_={
                "name": statement.excluded.name,
                "position": statement.excluded.position,
                "team": statement.excluded.team,
                "sleeper_id": sa.func.coalesce(
                    statement.excluded.sleeper_id, player_ids_table.c.sleeper_id
                ),
                "espn_id": sa.func.coalesce(statement.excluded.espn_id, player_ids_table.c.espn_id),
                "pfr_id": sa.func.coalesce(statement.excluded.pfr_id, player_ids_table.c.pfr_id),
                "cfb_player_id": sa.func.coalesce(
                    statement.excluded.cfb_player_id, player_ids_table.c.cfb_player_id
                ),
                "mfl_id": sa.func.coalesce(statement.excluded.mfl_id, player_ids_table.c.mfl_id),
                "fantasycalc_id": sa.func.coalesce(
                    statement.excluded.fantasycalc_id, player_ids_table.c.fantasycalc_id
                ),
                "merge_name": sa.func.coalesce(
                    statement.excluded.merge_name, player_ids_table.c.merge_name
                ),
            },
        )
        session.execute(statement, chunk)
    return len(rows)


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
    sleeper_players = get_players_nfl()

    warnings: list[str] = []
    sleeper_fetched_at = _sleeper_cache_fetched_at()
    if sleeper_fetched_at is None:
        sleeper_fetched_at = run_utc
        warnings.append("sleeper_players cache metadata unavailable; using run UTC")

    build = build_crosswalk_rows(players_rows, dp_rows, sleeper_players)
    upserted_count = upsert_player_ids(session, list(build.rows))

    report_warnings = warnings + list(build.warnings) + list(build.conflicts)
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
        warnings=tuple(report_warnings),
    )


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


def _apply_sleeper_enrich(
    rows_by_gsis: dict[str, dict[str, Any]],
    sleeper_players: dict[str, dict],
    warnings: list[str],
) -> int:
    applied_keys: set[str] = set()

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

    for gsis_id, entries in by_gsis.items():
        row = rows_by_gsis.get(gsis_id)
        if row is None:
            continue

        if len(entries) > 1:
            warnings.append(f"sleeper_multi_claim:gsis_id={gsis_id}")
            # Withhold sleeper_id; fill other NULL externals only when all agree.
            espn_values = {
                value
                for _pid, player in entries
                if (value := _normalize_identity(player.get("espn_id"))) is not None
            }
            if len(espn_values) == 1 and row["espn_id"] is None:
                row["espn_id"] = next(iter(espn_values))
                for pid, _player in entries:
                    applied_keys.add(pid)
            continue

        sleeper_pid, player = entries[0]
        filled = False
        if row["sleeper_id"] is None:
            row["sleeper_id"] = sleeper_pid
            filled = True
        espn_id = _normalize_identity(player.get("espn_id"))
        if row["espn_id"] is None and espn_id is not None:
            row["espn_id"] = espn_id
            filled = True
        if filled:
            applied_keys.add(sleeper_pid)

    # Exact sleeper_id key join for rows that already have sleeper_id (NULL-fill only).
    for row in rows_by_gsis.values():
        sleeper_id = row.get("sleeper_id")
        if sleeper_id is None:
            continue
        player = sleeper_players.get(str(sleeper_id))
        if not isinstance(player, dict):
            continue
        espn_id = _normalize_identity(player.get("espn_id"))
        if row["espn_id"] is None and espn_id is not None:
            row["espn_id"] = espn_id
            applied_keys.add(str(sleeper_id))

    return len(applied_keys)


def _sleeper_cache_fetched_at() -> datetime | None:
    """Read aware-UTC ``fetched_at`` from the K-03a cache metadata file."""
    try:
        from razzle_api.ingest import sleeper as sleeper_mod

        cache_dir = sleeper_mod._default_cache_dir()
        _data_path, meta_path = _players_paths(cache_dir)
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


def _chunks(rows: list[dict], size: int = 500) -> list[list[dict]]:
    return [rows[start : start + size] for start in range(0, len(rows), size)]
