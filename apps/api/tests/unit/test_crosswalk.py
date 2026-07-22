"""Unit tests for the canonical player identity crosswalk (K-03b)."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from razzle_api.config import get_settings
from razzle_api.ingest import crosswalk
from razzle_api.ingest.crosswalk import (
    DP_PLAYERIDS_URL,
    USER_AGENT,
    build_crosswalk_rows,
    fetch_db_playerids,
    player_ids_table,
    sync,
    upsert_player_ids,
)
from razzle_api.ingest.nflverse import upsert_players

API_DIR = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "crosswalk"
REPO_ROOT = API_DIR.parents[1]

_spec = importlib.util.spec_from_file_location(
    "verify_data", REPO_ROOT / "scripts" / "verify_data.py"
)
assert _spec is not None and _spec.loader is not None
verify_data = importlib.util.module_from_spec(_spec)
sys.modules["verify_data"] = verify_data
_spec.loader.exec_module(verify_data)

CheckStatus = verify_data.CheckStatus
compare_identity_capability = verify_data.compare_identity_capability

CANONICAL_PLAYERS = [
    {"gsis_id": "00-0001", "name": "Historical Only", "position": "WR", "team": "NYG"},
    {"gsis_id": "00-0002", "name": "Canonical Two", "position": "WR", "team": "KC"},
    {"gsis_id": "00-0003", "name": "Conflict Stub", "position": "QB", "team": "BUF"},
    {"gsis_id": "00-0004", "name": "Player Four", "position": "WR", "team": "MIA"},
    {"gsis_id": "00-0005", "name": "Player Five", "position": "RB", "team": "SF"},
    {"gsis_id": "00-0006", "name": "Player Six", "position": "TE", "team": "CHI"},
    {"gsis_id": "00-0007", "name": "Player Seven", "position": "WR", "team": "DAL"},
    {"gsis_id": "00-0008", "name": "Player Eight", "position": "TE", "team": "PHI"},
]


def _load_dp_fixture() -> list[dict]:
    with (FIXTURES / "db_playerids_sample.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_sleeper_fixture() -> dict[str, dict]:
    return json.loads((FIXTURES / "sleeper_players_sample.json").read_text(encoding="utf-8"))


def _by_gsis(rows: tuple[dict, ...] | list[dict]) -> dict[str, dict]:
    return {row["gsis_id"]: row for row in rows}


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'crosswalk.db'}"
    monkeypatch.setenv("RAZZLE_DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(API_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_DIR / "migrations"))
        cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        yield sessionmaker(engine, expire_on_commit=False)
        engine.dispose()
    finally:
        get_settings.cache_clear()


@pytest.fixture
def seeded_session(session_factory):
    with session_factory() as session:
        upsert_players(session, CANONICAL_PLAYERS)
        session.commit()
        yield session


@pytest.fixture
def built(seeded_session):
    return build_crosswalk_rows(
        CANONICAL_PLAYERS,
        _load_dp_fixture(),
        _load_sleeper_fixture(),
    )


def test_dp_playerids_url_and_user_agent() -> None:
    assert DP_PLAYERIDS_URL == (
        "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
    )
    assert USER_AGENT == "razzle-sync/1.0"


def test_fetch_db_playerids_is_bom_safe(monkeypatch) -> None:
    bom_csv = (
        "\ufeffgsis_id,sleeper_id,name,merge_name,position,team,espn_id,pfr_id,cfbref_id,mfl_id\n"
        "00-9,1,Bom Player,bom player,QB,NE,2,Pfr9,cfb-9,3\n"
    ).encode("utf-8")

    class _Resp:
        def read(self) -> bytes:
            return bom_csv

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(request, timeout=0):
        assert request.full_url == DP_PLAYERIDS_URL
        assert request.get_header("User-agent") == USER_AGENT
        assert timeout == 120
        return _Resp()

    monkeypatch.setattr(crosswalk.urllib.request, "urlopen", fake_urlopen)
    rows = fetch_db_playerids()
    assert rows == [
        {
            "gsis_id": "00-9",
            "sleeper_id": "1",
            "name": "Bom Player",
            "merge_name": "bom player",
            "position": "QB",
            "team": "NE",
            "espn_id": "2",
            "pfr_id": "Pfr9",
            "cfbref_id": "cfb-9",
            "mfl_id": "3",
        }
    ]


def test_spine_superset(built) -> None:
    gsis_ids = {row["gsis_id"] for row in built.rows}
    spine = {player["gsis_id"] for player in CANONICAL_PLAYERS}
    assert spine <= gsis_ids
    assert "MEN516487" in gsis_ids
    assert [row["gsis_id"] for row in built.rows] == sorted(gsis_ids)


def test_canonical_fields_win_and_drift_warns(built) -> None:
    row = _by_gsis(built.rows)["00-0002"]
    assert row["name"] == "Canonical Two"
    assert row["position"] == "WR"
    assert row["team"] == "KC"
    assert row["sleeper_id"] == "2002"
    assert row["espn_id"] == "3002"
    assert any("dp_identity_drift:gsis_id=00-0002" in item for item in built.warnings)
    assert "name" in next(item for item in built.warnings if "00-0002" in item)
    assert "position" in next(item for item in built.warnings if "00-0002" in item)


def test_conflict_stub_survives(built) -> None:
    row = _by_gsis(built.rows)["00-0003"]
    assert row["name"] == "Conflict Stub"
    assert row["position"] == "QB"
    assert row["team"] == "BUF"
    assert row["sleeper_id"] is None
    assert row["espn_id"] is None
    assert row["pfr_id"] is None
    assert row["cfb_player_id"] is None
    assert row["mfl_id"] is None
    assert any("dp_duplicate_conflict:gsis_id=00-0003" in item for item in built.conflicts)
    assert any("dp_duplicate_conflict:gsis_id=00-0003" in item for item in built.skipped)


def test_dp_only_insert(built) -> None:
    row = _by_gsis(built.rows)["MEN516487"]
    assert row["name"] == "Provisional Player"
    assert row["sleeper_id"] == "2999"
    assert row["position"] == "WR"
    assert row["team"] == "FA"
    assert any("dp_nameless:gsis_id=00-NONAME" in item for item in built.skipped)
    assert "00-NONAME" not in _by_gsis(built.rows)


def test_na_null_and_cfb_rename_and_fantasycalc_null(built) -> None:
    five = _by_gsis(built.rows)["00-0005"]
    # DP NA sleeper/espn become null before Sleeper null-fill.
    assert five["pfr_id"] == "Pfr05"
    assert five["cfb_player_id"] == "cfb-05"
    assert five["fantasycalc_id"] is None

    four = _by_gsis(built.rows)["00-0004"]
    assert four["cfb_player_id"] is None  # blank cfbref_id
    assert four["fantasycalc_id"] is None

    for row in built.rows:
        assert row["fantasycalc_id"] is None


def test_external_collisions_withheld_all(built) -> None:
    seven = _by_gsis(built.rows)["00-0007"]
    eight = _by_gsis(built.rows)["00-0008"]
    assert seven["sleeper_id"] is None
    assert eight["sleeper_id"] is None
    assert seven["espn_id"] == "3700"
    assert eight["espn_id"] == "3800"
    assert any(
        "external_collision:field=sleeper_id value=2700" in item for item in built.conflicts
    )


def test_exact_joins_only_no_name_match(built) -> None:
    two = _by_gsis(built.rows)["00-0002"]
    # Name-only sleeper entry 9999 must not attach.
    assert two["sleeper_id"] == "2002"
    assert two["espn_id"] == "3002"

    historical = _by_gsis(built.rows)["00-0001"]
    assert historical["sleeper_id"] is None
    assert historical["espn_id"] is None


def test_null_fill_only_never_overwrites_dp(built) -> None:
    two = _by_gsis(built.rows)["00-0002"]
    # Sleeper dump offers espn_id=9999 for the same gsis; DP already set 3002.
    assert two["espn_id"] == "3002"
    assert two["sleeper_id"] == "2002"

    five = _by_gsis(built.rows)["00-0005"]
    assert five["sleeper_id"] == "2505"
    assert five["espn_id"] == "3505"

    four = _by_gsis(built.rows)["00-0004"]
    assert four["sleeper_id"] == "2404"
    assert four["espn_id"] == "3404"

    six = _by_gsis(built.rows)["00-0006"]
    assert six["sleeper_id"] is None
    assert six["espn_id"] is None
    assert any("sleeper_multi_claim:gsis_id=00-0006" in item for item in built.warnings)


def test_empty_players_raises() -> None:
    with pytest.raises(ValueError, match="players table is empty"):
        build_crosswalk_rows([], _load_dp_fixture(), _load_sleeper_fixture())


def test_idempotent_rerun_never_blanks(seeded_session) -> None:
    build = build_crosswalk_rows(
        CANONICAL_PLAYERS,
        _load_dp_fixture(),
        _load_sleeper_fixture(),
    )
    first = upsert_player_ids(seeded_session, list(build.rows))
    seeded_session.commit()
    assert first == len(build.rows)

    blanked = []
    for row in build.rows:
        blanked.append(
            {
                **row,
                "sleeper_id": None,
                "espn_id": None,
                "pfr_id": None,
                "cfb_player_id": None,
                "mfl_id": None,
                "fantasycalc_id": None,
                "merge_name": None,
            }
        )
    upsert_player_ids(seeded_session, blanked)
    seeded_session.commit()

    stored = {
        row["gsis_id"]: dict(row)
        for row in seeded_session.execute(sa.select(player_ids_table)).mappings()
    }
    original = _by_gsis(build.rows)
    for gsis_id, expected in original.items():
        got = stored[gsis_id]
        assert got["name"] == expected["name"]
        assert got["position"] == expected["position"]
        assert got["team"] == expected["team"]
        for field in (
            "sleeper_id",
            "espn_id",
            "pfr_id",
            "cfb_player_id",
            "mfl_id",
            "fantasycalc_id",
            "merge_name",
        ):
            assert got[field] == expected[field]


def test_sync_report_stamps_counts_timestamps(seeded_session, monkeypatch) -> None:
    dp_rows = _load_dp_fixture()
    sleeper_players = _load_sleeper_fixture()
    run_utc = datetime(2026, 7, 22, 18, 0, tzinfo=UTC)
    cache_utc = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)

    monkeypatch.setattr(crosswalk, "fetch_db_playerids", lambda: dp_rows)
    monkeypatch.setattr(crosswalk, "get_players_nfl", lambda: sleeper_players)
    monkeypatch.setattr(crosswalk, "_sleeper_cache_fetched_at", lambda: cache_utc)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return run_utc

    monkeypatch.setattr(crosswalk, "datetime", _FrozenDatetime)

    report = sync(seeded_session, seasons=[2024, 2025])
    seeded_session.commit()

    assert report.adapter == "crosswalk"
    build = build_crosswalk_rows(CANONICAL_PLAYERS, dp_rows, sleeper_players)
    assert report.upserted == {"player_ids": len(build.rows)}
    assert report.stamps[0].source == "dynastyprocess_playerids"
    assert report.stamps[0].season is None
    assert report.stamps[0].rows == build.accepted_dp_rows
    assert report.stamps[0].fetched_at == run_utc
    assert report.stamps[1].source == "sleeper_players"
    assert report.stamps[1].season is None
    assert report.stamps[1].rows == build.applied_sleeper_rows
    assert report.stamps[1].fetched_at == cache_utc
    assert report.skipped == build.skipped

    # Corrupt / missing cache metadata falls back to run UTC with a warning.
    monkeypatch.setattr(crosswalk, "_sleeper_cache_fetched_at", lambda: None)
    report_fallback = sync(seeded_session)
    assert report_fallback.stamps[1].fetched_at == run_utc
    assert any("cache metadata unavailable" in item for item in report_fallback.warnings)


def test_upsert_then_identity_capability_pass(seeded_session) -> None:
    build = build_crosswalk_rows(
        CANONICAL_PLAYERS,
        _load_dp_fixture(),
        _load_sleeper_fixture(),
    )
    upsert_player_ids(seeded_session, list(build.rows))
    seeded_session.commit()

    identity_rows = [
        dict(row) for row in seeded_session.execute(sa.select(player_ids_table)).mappings()
    ]
    canonical_ids = [player["gsis_id"] for player in CANONICAL_PLAYERS]
    result = compare_identity_capability(canonical_ids, identity_rows)
    assert result.status == CheckStatus.PASS

    # Real table columns include gsis_id; every spine id is present.
    present = {row["gsis_id"] for row in identity_rows}
    assert set(canonical_ids) <= present


def test_sync_empty_players_raises(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(crosswalk, "fetch_db_playerids", lambda: _load_dp_fixture())
    monkeypatch.setattr(crosswalk, "get_players_nfl", lambda: _load_sleeper_fixture())
    with session_factory() as session:
        with pytest.raises(ValueError, match="players table is empty"):
            sync(session)


def test_player_ids_table_matches_migration_shape() -> None:
    columns = {column.name for column in player_ids_table.columns}
    assert columns == {
        "gsis_id",
        "sleeper_id",
        "espn_id",
        "pfr_id",
        "cfb_player_id",
        "mfl_id",
        "fantasycalc_id",
        "name",
        "merge_name",
        "position",
        "team",
    }
