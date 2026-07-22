"""Unit tests for the canonical player identity crosswalk (K-03b)."""

from __future__ import annotations

import csv
import importlib.util
import json
import random
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


def _stored_player_ids(session) -> dict[str, dict]:
    return {
        row["gsis_id"]: dict(row) for row in session.execute(sa.select(player_ids_table)).mappings()
    }


def _player_ids_count(session) -> int:
    return int(
        session.execute(sa.select(sa.func.count()).select_from(player_ids_table)).scalar_one()
    )


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
    # Agreeing DP duplicates (identical incl. mfl_id): NA sleeper/espn null-filled by Sleeper.
    assert five["mfl_id"] == "107"
    assert five["pfr_id"] == "Pfr05"
    assert five["cfb_player_id"] == "cfb-05"
    assert five["fantasycalc_id"] is None
    assert five["sleeper_id"] == "2505"
    assert five["espn_id"] == "3505"

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
    assert any("external_collision:field=sleeper_id value=2700" in item for item in built.conflicts)


def test_exact_joins_only_no_name_match(built) -> None:
    two = _by_gsis(built.rows)["00-0002"]
    # Name-only sleeper entry 9999 must not attach.
    assert two["sleeper_id"] == "2002"
    assert two["espn_id"] == "3002"

    historical = _by_gsis(built.rows)["00-0001"]
    # No name join; multi-claim leaves sleeper_id NULL (no DP sleeper_id).
    assert historical["sleeper_id"] is None
    assert historical["espn_id"] == "3100"  # agreeing multi-claim espn null-fill


def test_null_fill_only_never_overwrites_dp(built) -> None:
    two = _by_gsis(built.rows)["00-0002"]
    # Sleeper multi-claim offers conflicting espn; DP espn retained.
    assert two["espn_id"] == "3002"
    assert two["sleeper_id"] == "2002"

    five = _by_gsis(built.rows)["00-0005"]
    assert five["sleeper_id"] == "2505"
    assert five["espn_id"] == "3505"

    four = _by_gsis(built.rows)["00-0004"]
    assert four["sleeper_id"] == "2404"
    assert four["espn_id"] == "3404"


def test_sleeper_multi_claim_retains_dp_sleeper_id(built) -> None:
    """Authoritative DP sleeper_id survives multi-claim; ambiguous Sleeper fill withheld."""
    two = _by_gsis(built.rows)["00-0002"]
    assert two["sleeper_id"] == "2002"
    assert any("sleeper_multi_claim:gsis_id=00-0002" in item for item in built.warnings)

    six = _by_gsis(built.rows)["00-0006"]
    assert six["sleeper_id"] is None
    assert six["espn_id"] is None
    assert any("sleeper_multi_claim:gsis_id=00-0006" in item for item in built.warnings)

    historical = _by_gsis(built.rows)["00-0001"]
    assert historical["sleeper_id"] is None
    assert any("sleeper_multi_claim:gsis_id=00-0001" in item for item in built.warnings)


def test_applied_sleeper_rows_counts_unique_contributors(built) -> None:
    # Unique fills: 2505 (00-0005), 2404 (00-0004), one of 2610/2611 (00-0001 agree espn).
    # Multi-claim on 00-0002 and 00-0006 contribute no unique sleeper_id fill.
    assert built.applied_sleeper_rows == 3

    # Agreeing multi-claim espn fill counts once, not once per claimant.
    players = CANONICAL_PLAYERS
    dp_rows = _load_dp_fixture()
    sleeper = {
        "9001": {"player_id": "9001", "gsis_id": "00-0006", "espn_id": "9100"},
        "9002": {"player_id": "9002", "gsis_id": "00-0006", "espn_id": "9100"},
    }
    only_multi = build_crosswalk_rows(players, dp_rows, sleeper)
    six = _by_gsis(only_multi.rows)["00-0006"]
    assert six["sleeper_id"] is None
    assert six["espn_id"] == "9100"
    # Baseline fixture applied 3 using other entries; isolate: only this multi agree-fill.
    isolated = build_crosswalk_rows(
        [{"gsis_id": "00-0006", "name": "Player Six", "position": "TE", "team": "CHI"}],
        [],
        sleeper,
    )
    assert isolated.applied_sleeper_rows == 1


def test_shuffled_dp_input_is_deterministic() -> None:
    sleeper = _load_sleeper_fixture()
    base_dp = _load_dp_fixture()
    baseline = build_crosswalk_rows(CANONICAL_PLAYERS, base_dp, sleeper)

    for seed in (0, 1, 7, 42):
        shuffled = list(base_dp)
        random.Random(seed).shuffle(shuffled)
        built = build_crosswalk_rows(CANONICAL_PLAYERS, shuffled, sleeper)
        assert built.rows == baseline.rows
        assert built.skipped == baseline.skipped
        assert built.warnings == baseline.warnings
        assert built.conflicts == baseline.conflicts
        assert built.accepted_dp_rows == baseline.accepted_dp_rows
        assert built.applied_sleeper_rows == baseline.applied_sleeper_rows
        assert built.skipped == tuple(sorted(set(built.skipped)))
        assert built.warnings == tuple(sorted(set(built.warnings)))
        assert built.conflicts == tuple(sorted(set(built.conflicts)))


def test_empty_players_raises() -> None:
    with pytest.raises(ValueError, match="players table is empty"):
        build_crosswalk_rows([], _load_dp_fixture(), _load_sleeper_fixture())


def test_identical_rerun_stable(seeded_session) -> None:
    build = build_crosswalk_rows(
        CANONICAL_PLAYERS,
        _load_dp_fixture(),
        _load_sleeper_fixture(),
    )
    upsert_player_ids(seeded_session, list(build.rows))
    seeded_session.commit()
    first = _stored_player_ids(seeded_session)

    upsert_player_ids(seeded_session, list(build.rows))
    seeded_session.commit()
    second = _stored_player_ids(seeded_session)
    assert second == first


def test_durable_withholding_clears_prior_ids_on_dp_conflict(seeded_session) -> None:
    """Newly detected DP duplicate conflict clears previously verified externals."""
    clean_dp = [
        {
            "mfl_id": "103",
            "gsis_id": "00-0003",
            "sleeper_id": "2100",
            "espn_id": "3100",
            "pfr_id": "Pfr03",
            "cfbref_id": "cfb-03",
            "name": "Conflict Stub",
            "merge_name": "conflict stub",
            "position": "QB",
            "team": "BUF",
        }
    ]
    first = build_crosswalk_rows(CANONICAL_PLAYERS, clean_dp, {})
    upsert_player_ids(seeded_session, list(first.rows))
    seeded_session.commit()
    stored = _stored_player_ids(seeded_session)["00-0003"]
    assert stored["sleeper_id"] == "2100"
    assert stored["espn_id"] == "3100"
    assert stored["merge_name"] == "conflict stub"

    conflict_dp = [
        {**clean_dp[0], "sleeper_id": "2100", "espn_id": "3100"},
        {
            **clean_dp[0],
            "sleeper_id": "2101",
            "espn_id": "3101",
            "pfr_id": "Pfr03b",
            "merge_name": "conflict other",
        },
    ]
    second = build_crosswalk_rows(CANONICAL_PLAYERS, conflict_dp, {})
    upsert_player_ids(seeded_session, list(second.rows))
    seeded_session.commit()

    cleared = _stored_player_ids(seeded_session)["00-0003"]
    assert cleared["name"] == "Conflict Stub"
    assert cleared["position"] == "QB"
    assert cleared["team"] == "BUF"
    assert cleared["sleeper_id"] is None
    assert cleared["espn_id"] is None
    assert cleared["pfr_id"] is None
    assert cleared["cfb_player_id"] is None
    assert cleared["mfl_id"] is None
    assert cleared["merge_name"] is None
    assert "00-0003" in _stored_player_ids(seeded_session)


def test_durable_withholding_clears_prior_ids_on_external_collision(seeded_session) -> None:
    """Cross-source external collision clears contested IDs; stubs survive."""
    solo_dp = [
        {
            "mfl_id": "105",
            "gsis_id": "00-0007",
            "sleeper_id": "2700",
            "espn_id": "3700",
            "pfr_id": "Pfr07",
            "cfbref_id": "cfb-07",
            "name": "Player Seven",
            "merge_name": "player seven",
            "position": "WR",
            "team": "DAL",
        }
    ]
    first = build_crosswalk_rows(CANONICAL_PLAYERS, solo_dp, {})
    upsert_player_ids(seeded_session, list(first.rows))
    seeded_session.commit()
    assert _stored_player_ids(seeded_session)["00-0007"]["sleeper_id"] == "2700"

    collision_dp = [
        solo_dp[0],
        {
            "mfl_id": "106",
            "gsis_id": "00-0008",
            "sleeper_id": "2700",
            "espn_id": "3800",
            "pfr_id": "Pfr08",
            "cfbref_id": "cfb-08",
            "name": "Player Eight",
            "merge_name": "player eight",
            "position": "TE",
            "team": "PHI",
        },
    ]
    second = build_crosswalk_rows(CANONICAL_PLAYERS, collision_dp, {})
    upsert_player_ids(seeded_session, list(second.rows))
    seeded_session.commit()

    stored = _stored_player_ids(seeded_session)
    assert stored["00-0007"]["sleeper_id"] is None
    assert stored["00-0008"]["sleeper_id"] is None
    assert stored["00-0007"]["name"] == "Player Seven"
    assert stored["00-0008"]["name"] == "Player Eight"
    assert stored["00-0007"]["espn_id"] == "3700"
    assert stored["00-0008"]["espn_id"] == "3800"


def _patch_sync_sources(monkeypatch, dp_rows, sleeper_players, *, cache_at=None) -> None:
    def fetch_dp():
        return dp_rows

    def fetch_sleeper():
        return sleeper_players

    def cache_fetched_at():
        return cache_at

    monkeypatch.setattr(crosswalk, "fetch_db_playerids", fetch_dp)
    monkeypatch.setattr(crosswalk.sleeper_mod, "get_players_nfl", fetch_sleeper)
    monkeypatch.setattr(crosswalk, "_sleeper_cache_fetched_at", cache_fetched_at)


def test_sync_report_stamps_counts_timestamps(seeded_session, monkeypatch) -> None:
    dp_rows = _load_dp_fixture()
    sleeper_players = _load_sleeper_fixture()
    run_utc = datetime(2026, 7, 22, 18, 0, tzinfo=UTC)
    cache_utc = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    _patch_sync_sources(monkeypatch, dp_rows, sleeper_players, cache_at=cache_utc)

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
    assert report.warnings == tuple(sorted(set(report.warnings)))

    _patch_sync_sources(monkeypatch, dp_rows, sleeper_players, cache_at=None)
    report_fallback = sync(seeded_session)
    assert report_fallback.stamps[1].fetched_at == run_utc
    assert any("cache metadata unavailable" in item for item in report_fallback.warnings)


def test_fetch_failure_writes_no_player_ids(seeded_session, monkeypatch) -> None:
    assert _player_ids_count(seeded_session) == 0

    def boom_dp():
        raise RuntimeError("dp network down")

    monkeypatch.setattr(crosswalk, "fetch_db_playerids", boom_dp)
    monkeypatch.setattr(crosswalk.sleeper_mod, "get_players_nfl", _load_sleeper_fixture)

    with pytest.raises(RuntimeError, match="dp network down"):
        sync(seeded_session)
    assert _player_ids_count(seeded_session) == 0

    def ok_dp():
        return _load_dp_fixture()

    def boom_sleeper():
        raise RuntimeError("sleeper network down")

    monkeypatch.setattr(crosswalk, "fetch_db_playerids", ok_dp)
    monkeypatch.setattr(crosswalk.sleeper_mod, "get_players_nfl", boom_sleeper)

    with pytest.raises(RuntimeError, match="sleeper network down"):
        sync(seeded_session)
    assert _player_ids_count(seeded_session) == 0


def test_upsert_then_identity_capability_pass(seeded_session) -> None:
    build = build_crosswalk_rows(
        CANONICAL_PLAYERS,
        _load_dp_fixture(),
        _load_sleeper_fixture(),
    )
    upsert_player_ids(seeded_session, list(build.rows))
    seeded_session.commit()

    identity_rows = list(_stored_player_ids(seeded_session).values())
    canonical_ids = [player["gsis_id"] for player in CANONICAL_PLAYERS]
    result = compare_identity_capability(canonical_ids, identity_rows)
    assert result.status == CheckStatus.PASS

    present = {row["gsis_id"] for row in identity_rows}
    assert set(canonical_ids) <= present


def test_sync_empty_players_raises(session_factory, monkeypatch) -> None:
    _patch_sync_sources(monkeypatch, _load_dp_fixture(), _load_sleeper_fixture())
    with session_factory() as session:
        with pytest.raises(ValueError, match="players table is empty"):
            sync(session)
        assert _player_ids_count(session) == 0


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
