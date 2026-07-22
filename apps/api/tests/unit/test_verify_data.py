"""Offline unit tests for scripts/verify_data.py (Stage 0 G6 harness)."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from razzle_api.config import get_settings
from razzle_api.ingest.nflverse import (
    STAT_COLUMNS,
    map_player_row,
    map_week_row,
    upsert_players,
    upsert_week_stats,
)
from razzle_api.ingest.report import SourceStamp, stamp_source_syncs


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "verify_data.py"
        if candidate.is_file():
            return parent
    raise RuntimeError("could not locate repository root with scripts/verify_data.py")


REPO_ROOT = _repo_root()
API_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_data.py"

_spec = importlib.util.spec_from_file_location("verify_data", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
verify_data = importlib.util.module_from_spec(_spec)
sys.modules["verify_data"] = verify_data
_spec.loader.exec_module(verify_data)

CheckStatus = verify_data.CheckStatus
compare_freshness_capability = verify_data.compare_freshness_capability
compare_identity_capability = verify_data.compare_identity_capability
format_human_report = verify_data.format_human_report
read_csv_rows = verify_data.read_csv_rows
run_cli = verify_data.run_cli
verify = verify_data.verify

SEASON = 2024
SEED = 20260722
SAMPLE = 3

# Independently pinned expectations (not derived from map_* alone).
PINNED_NEW = {
    "player_id": "00-0034796",
    "week": 3,
    "pass_att": 30.0,
    "pass_cmp": 22.0,
    "pass_yd": 275.0,
    "pass_td": 2.0,
    "pass_int": 1.0,
    "pass_sack": 3.0,
    "pass_two_pt": 1.0,
    "rush_att": 8.0,
    "rush_yd": 45.0,
    "rush_td": 1.0,
    "rush_two_pt": 0.0,
    "target": 0.0,
    "rec": 0.0,
    "rec_yd": 0.0,
    "rec_td": 0.0,
    "rec_two_pt": 0.0,
    "fumble": 2.0,
    "fumble_lost": 1.0,
    "return_yd": 0.0,
    "return_td": 0.0,
    "special_teams_td": 2.0,
    "pat_made": 0.0,
    "pat_missed": 0.0,
    "fg_made": 0.0,
    "fg_missed": 0.0,
}

PINNED_OLD = dict(PINNED_NEW)


def _player_raw(
    gsis_id: str,
    *,
    name: str,
    position: str = "QB",
    team: str | None = "KC",
) -> dict[str, str]:
    return {
        "gsis_id": gsis_id,
        "display_name": name,
        "position": position,
        "latest_team": "" if team is None else team,
    }


def _week_raw_new(
    player_id: str,
    *,
    week: int = 3,
    season: int = SEASON,
    position: str = "QB",
    season_type: str = "REG",
    **overrides: str,
) -> dict[str, str]:
    row = {
        "player_id": player_id,
        "position": position,
        "season": str(season),
        "week": str(week),
        "season_type": season_type,
        "completions": "22",
        "attempts": "30",
        "passing_yards": "275",
        "passing_tds": "2",
        "passing_interceptions": "1",
        "sacks_suffered": "3",
        "passing_2pt_conversions": "1",
        "carries": "8",
        "rushing_yards": "45",
        "rushing_tds": "1",
        "rushing_2pt_conversions": "0",
        "targets": "0",
        "receptions": "0",
        "receiving_yards": "0",
        "receiving_tds": "0",
        "receiving_2pt_conversions": "0",
        "rushing_fumbles": "1",
        "receiving_fumbles": "0",
        "sack_fumbles": "1",
        "rushing_fumbles_lost": "1",
        "receiving_fumbles_lost": "0",
        "sack_fumbles_lost": "0",
        "special_teams_tds": "2",
    }
    row.update(overrides)
    return row


def _week_raw_old(player_id: str, **overrides: str) -> dict[str, str]:
    row = _week_raw_new(player_id, **overrides)
    row.pop("passing_interceptions", None)
    row.pop("sacks_suffered", None)
    row["interceptions"] = overrides.get("interceptions", "1")
    row["sacks"] = overrides.get("sacks", "3")
    return row


def _fixture_players() -> list[dict[str, str]]:
    return [
        _player_raw("00-0000001", name="Alpha One", position="QB", team="KC"),
        _player_raw("00-0000002", name="Bravo Two", position="RB", team="SF"),
        _player_raw("00-0000003", name="Charlie Three", position="WR", team="BUF"),
        _player_raw("00-0000004", name="Delta Four", position="TE", team=None),
        _player_raw("00-0000005", name="Echo Five", position="RB", team="DET"),
        _player_raw("00-0034796", name="Pinned Passer", position="QB", team="KC"),
        # Rejected by map (usable identity for negative audit).
        _player_raw("00-0099991", name="Kicker", position="K", team="DAL"),
    ]


def _fixture_weeks() -> list[dict[str, str]]:
    rows = [
        _week_raw_old("00-0000001", week=1, position="QB"),
        _week_raw_new("00-0000002", week=1, position="RB", attempts="0", completions="0"),
        _week_raw_new("00-0000003", week=1, position="WR", attempts="0", completions="0"),
        _week_raw_new("00-0000004", week=1, position="TE", attempts="0", completions="0"),
        _week_raw_new("00-0000005", week=1, position="RB", attempts="0", completions="0"),
        _week_raw_new("00-0034796", week=3, position="QB"),
        # Rejected: POST and K.
        _week_raw_new("00-0000001", week=18, position="QB", season_type="POST"),
        _week_raw_new("00-0099991", week=1, position="K"),
    ]
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    assert rows
    fieldnames = list(rows[0].keys())
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    # BOM-safe write to match nflverse players.csv.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    db_path = tmp_path / "verify.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("RAZZLE_DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(API_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_DIR / "migrations"))
        cfg.set_main_option("sqlalchemy.url", db_url)
        # Most R-03 tests exercise the pre-K-01 unavailable-capability state.
        command.upgrade(cfg, "0001")
        engine = sa.create_engine(db_url)
        factory = sessionmaker(engine, expire_on_commit=False)
        yield {
            "db_path": db_path,
            "db_url": db_url,
            "engine": engine,
            "factory": factory,
            "tmp_path": tmp_path,
        }
        engine.dispose()
    finally:
        get_settings.cache_clear()


def _seed_from_source(
    factory,
    player_rows: list[dict[str, str]],
    week_rows: list[dict[str, str]],
    *,
    season: int = SEASON,
) -> None:
    players = [mapped for mapped in (map_player_row(row) for row in player_rows) if mapped]
    weeks = [mapped for mapped in (map_week_row(row) for row in week_rows) if mapped]
    with factory() as session:
        upsert_players(session, players)
        upsert_week_stats(session, season, weeks)
        session.commit()


def _block_network(monkeypatch) -> None:
    def _boom(*_args, **_kwargs):
        raise AssertionError("network fetch must not be called")

    monkeypatch.setattr(verify_data, "fetch_players", _boom)
    monkeypatch.setattr(verify_data, "fetch_week_stats", _boom)


def _run_verify(  # noqa: PLR0913
    factory,
    player_rows: list[dict[str, str]],
    week_rows: list[dict[str, str]],
    *,
    sample_size: int = SAMPLE,
    seed: int = SEED,
    seasons: list[int] | None = None,
    required_checks: set[str] | None = None,
    max_age_hours: float = 36.0,
    fetched_at: datetime | None = None,
):
    with factory() as session:
        return verify(
            session,
            sample_size=sample_size,
            seed=seed,
            seasons=seasons or [SEASON],
            player_source_rows=player_rows,
            week_source_rows_by_season={SEASON: week_rows},
            required_checks=required_checks or set(),
            max_age_hours=max_age_hours,
            fetched_at=fetched_at or datetime(2026, 7, 22, tzinfo=UTC),
        )


def _result(report, name: str, *, season: int | None = None):
    for item in report.results:
        if item.name != name:
            continue
        if season is not None and item.season != season:
            continue
        return item
    raise AssertionError(f"missing result {name} season={season}")


def test_happy_bidirectional_replay_with_pinned_map_fields(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    # Independent pinned oracle for old/new interception/sack names, two-point,
    # fumble sum, and special_teams_td.
    mapped_new = map_week_row(_week_raw_new("00-0034796"))
    mapped_old = map_week_row(_week_raw_old("00-0034796"))
    assert mapped_new == PINNED_NEW
    assert mapped_old == PINNED_OLD
    assert mapped_new["pass_int"] == 1.0
    assert mapped_new["pass_sack"] == 3.0
    assert mapped_new["pass_two_pt"] == 1.0
    assert mapped_new["fumble"] == 2.0
    assert mapped_new["special_teams_td"] == 2.0

    report = _run_verify(db_env["factory"], players, weeks)
    assert report.status == CheckStatus.PASS
    players_result = _result(report, "players")
    weeks_result = _result(report, "player_week_stats", season=SEASON)
    assert players_result.db_to_source_ok == SAMPLE
    assert players_result.source_to_db_ok == SAMPLE
    assert players_result.mismatch_count == 0
    assert weeks_result.db_to_source_ok == SAMPLE
    assert weeks_result.source_to_db_ok == SAMPLE
    assert weeks_result.mismatch_count == 0
    assert players_result.filter_leaks == 0
    assert players_result.total_failures == 0
    assert weeks_result.filter_leaks == 0
    assert weeks_result.integrity_mismatches == 0
    assert weeks_result.total_failures == 0
    assert _result(report, "identity").status == CheckStatus.UNAVAILABLE
    assert _result(report, "freshness").status == CheckStatus.UNAVAILABLE
    assert _result(report, "cross_source").status == CheckStatus.UNAVAILABLE


def test_required_freshness_passes_after_k01_stamps(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_env["db_url"])
    command.upgrade(cfg, "head")

    as_of = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    player_count = sum(map_player_row(row) is not None for row in players)
    week_count = sum(map_week_row(row) is not None for row in weeks)
    with db_env["factory"]() as session:
        stamp_source_syncs(
            session,
            (
                SourceStamp("nflverse_players", None, player_count, as_of),
                SourceStamp("nflverse_week_stats", SEASON, week_count, as_of),
            ),
        )
        session.commit()

    report = _run_verify(
        db_env["factory"],
        players,
        weeks,
        required_checks={"freshness"},
        fetched_at=as_of,
    )

    assert report.status == CheckStatus.PASS
    assert _result(report, "freshness").status == CheckStatus.PASS


def test_stat_and_player_corruption_fail_with_field_and_key(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    with db_env["factory"]() as session:
        session.execute(
            sa.text("UPDATE player_week_stats SET pass_yd = 999 WHERE player_id = '00-0034796'")
        )
        session.execute(
            sa.text(
                "UPDATE players SET name = 'Wrong', position = 'RB', team = 'XX' "
                "WHERE gsis_id = '00-0000001'"
            )
        )
        session.commit()

    report = _run_verify(db_env["factory"], players, weeks, sample_size=6)
    assert report.status == CheckStatus.FAIL
    week_details = "\n".join(_result(report, "player_week_stats", season=SEASON).details)
    player_details = "\n".join(_result(report, "players").details)
    assert "field=pass_yd" in week_details
    assert "00-0034796" in week_details
    assert "field=name" in player_details or "field=position" in player_details
    assert "00-0000001" in player_details


def test_missing_orphan_week_player_and_position_failures(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    # Equal-sized surfaces with divergent keys: one source-only, one DB-only.
    source_divergent = [
        row for row in weeks if not (row["player_id"] == "00-0000004" and row["week"] == "1")
    ] + [_week_raw_new("00-0000002", week=9, position="RB")]
    with db_env["factory"]() as session:
        session.execute(
            sa.text("DELETE FROM player_week_stats WHERE player_id = '00-0000004' AND week = 1")
        )
        upsert_week_stats(
            session,
            SEASON,
            [
                {
                    "player_id": "00-0000001",
                    "week": 12,
                    **{column: 0.0 for column in STAT_COLUMNS},
                }
            ],
        )
        session.commit()

    report = _run_verify(db_env["factory"], players, source_divergent, sample_size=6)
    assert report.status == CheckStatus.FAIL
    details = "\n".join(_result(report, "player_week_stats", season=SEASON).details)
    assert "db=missing" in details
    assert "00-0000002" in details
    assert "source=missing" in details

    # Week player missing: single accepted week whose player row is absent.
    with db_env["factory"]() as session:
        session.execute(sa.text("DELETE FROM player_week_stats"))
        session.execute(sa.text("DELETE FROM players"))
        session.commit()
    players_for_missing = [
        _player_raw("00-0000001", name="Alpha One", position="QB", team="KC"),
        _player_raw("00-0000003", name="Charlie Three", position="WR", team="BUF"),
        _player_raw("00-0099991", name="Kicker", position="K", team="DAL"),
    ]
    weeks_for_missing = [
        _week_raw_new("00-0000003", week=1, position="WR"),
        _week_raw_new("00-0000001", week=18, season_type="POST"),
    ]
    _seed_from_source(db_env["factory"], players_for_missing, weeks_for_missing)
    with db_env["factory"]() as session:
        session.execute(sa.text("DELETE FROM players WHERE gsis_id = '00-0000003'"))
        session.commit()
    source_players_ok = [
        _player_raw("00-0000001", name="Alpha One", position="QB", team="KC"),
        _player_raw("00-0099991", name="Kicker", position="K", team="DAL"),
    ]
    report = _run_verify(
        db_env["factory"],
        source_players_ok,
        weeks_for_missing,
        sample_size=1,
    )
    assert report.status == CheckStatus.FAIL
    details = "\n".join(_result(report, "player_week_stats", season=SEASON).details)
    assert "field=player_id" in details
    assert "00-0000003" in details

    # Position mismatch between players row and raw week position.
    with db_env["factory"]() as session:
        session.execute(sa.text("DELETE FROM player_week_stats"))
        session.execute(sa.text("DELETE FROM players"))
        session.commit()
    players2 = _fixture_players()
    weeks2 = _fixture_weeks()
    _seed_from_source(db_env["factory"], players2, weeks2)
    with db_env["factory"]() as session:
        session.execute(sa.text("UPDATE players SET position = 'WR' WHERE gsis_id = '00-0034796'"))
        session.commit()
    report = _run_verify(db_env["factory"], players2, weeks2, sample_size=6)
    assert report.status == CheckStatus.FAIL
    details = "\n".join(_result(report, "player_week_stats", season=SEASON).details)
    assert "field=position" in details
    assert "00-0034796" in details


def test_season_mismatch_and_filter_leaks_fail(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    bad_season = [_week_raw_new("00-0000001", week=1, season=1999)]
    report = _run_verify(db_env["factory"], players, bad_season + weeks[1:], sample_size=3)
    assert report.status == CheckStatus.FAIL
    details = "\n".join(_result(report, "player_week_stats", season=SEASON).details)
    assert "field=season" in details

    # POST leak into DB.
    post = _week_raw_new("00-0000001", week=18, season_type="POST")
    with db_env["factory"]() as session:
        upsert_week_stats(
            session,
            SEASON,
            [
                {
                    "player_id": "00-0000001",
                    "week": 18,
                    **{column: 0.0 for column in STAT_COLUMNS},
                }
            ],
        )
        session.commit()
    report = _run_verify(db_env["factory"], players, weeks + [post], sample_size=5)
    assert report.status == CheckStatus.FAIL
    details = "\n".join(_result(report, "player_week_stats", season=SEASON).details)
    assert "filter_leak" in details

    # K filter leak into players.
    with db_env["factory"]() as session:
        upsert_players(
            session,
            [{"gsis_id": "00-0099991", "name": "Kicker", "position": "K", "team": "DAL"}],
        )
        session.commit()
    # Direct insert of non-fantasy position via SQL because upsert uses mapped rows.
    with db_env["factory"]() as session:
        session.execute(
            sa.text(
                "INSERT OR REPLACE INTO players (gsis_id, name, position, team) "
                "VALUES ('00-0099991', 'Kicker', 'K', 'DAL')"
            )
        )
        session.commit()
    report = _run_verify(db_env["factory"], players, weeks, sample_size=5)
    assert report.status == CheckStatus.FAIL
    players_result = _result(report, "players")
    details = "\n".join(players_result.details)
    assert "filter_leak" in details
    assert players_result.filter_leaks == 1


def test_duplicate_keys_conflict_fail_identical_warn(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()

    conflict_players = players + [
        _player_raw("00-0000001", name="Alpha Conflict", position="QB", team="KC")
    ]
    _seed_from_source(db_env["factory"], players, weeks)
    report = _run_verify(db_env["factory"], conflict_players, weeks)
    assert report.status == CheckStatus.FAIL
    details = "\n".join(_result(report, "players").details)
    assert "duplicate" in details
    assert "00-0000001" in details

    identical_players = players + [
        _player_raw("00-0000001", name="Alpha One", position="QB", team="KC")
    ]
    report = _run_verify(db_env["factory"], identical_players, weeks)
    assert report.status == CheckStatus.PASS
    warnings = "\n".join(_result(report, "players").warnings)
    assert "identical duplicate" in warnings


def test_na_empty_nan_and_nullable_team_pass(db_env):
    players = [
        _player_raw("00-0000001", name="Alpha One", position="QB", team=None),
        _player_raw("00-0000002", name="Bravo Two", position="RB", team="SF"),
        _player_raw("00-0000003", name="Charlie Three", position="WR", team="BUF"),
        _player_raw("00-0099991", name="Kicker", position="K", team="DAL"),
    ]
    weeks = [
        _week_raw_new(
            "00-0000001",
            week=1,
            passing_yards="NA",
            rushing_yards="",
            targets="NaN",
            special_teams_tds="0",
            passing_2pt_conversions="0",
            rushing_fumbles="NA",
            receiving_fumbles="",
            sack_fumbles="NaN",
            rushing_fumbles_lost="0",
            receiving_fumbles_lost="0",
            sack_fumbles_lost="0",
        ),
        _week_raw_new("00-0000002", week=1, position="RB"),
        _week_raw_new("00-0000003", week=1, position="WR"),
        _week_raw_new("00-0000001", week=18, season_type="POST"),
    ]
    _seed_from_source(db_env["factory"], players, weeks)
    report = _run_verify(db_env["factory"], players, weeks)
    assert report.status == CheckStatus.PASS
    mapped = map_week_row(weeks[0])
    assert mapped is not None
    assert mapped["pass_yd"] == 0.0
    assert mapped["rush_yd"] == 0.0
    assert mapped["target"] == 0.0
    assert mapped["fumble"] == 0.0
    assert map_player_row(players[0])["team"] is None


def test_seed_stability_and_undersized_fail(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    report_a = _run_verify(db_env["factory"], players, weeks, seed=SEED)
    report_b = _run_verify(db_env["factory"], players, weeks, seed=SEED)
    assert report_a.sample_keys == report_b.sample_keys
    assert report_a.sample_keys["players.db_to_source"]
    assert report_a.sample_keys["players.source_to_db"]

    report_small = _run_verify(db_env["factory"], players, weeks, sample_size=50)
    assert report_small.status == CheckStatus.FAIL
    assert "undersized" in _result(report_small, "players").message

    with db_env["factory"]() as session:
        session.execute(sa.text("DELETE FROM players"))
        session.execute(sa.text("DELETE FROM player_week_stats"))
        session.commit()
    report_empty = _run_verify(db_env["factory"], players, weeks, sample_size=1)
    assert report_empty.status == CheckStatus.FAIL


def test_offline_missing_source_and_live_fetch_error(db_env, monkeypatch, capsys):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)
    _block_network(monkeypatch)

    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--sample",
            "3",
            "--seasons",
            str(SEASON),
        ]
    )
    err = capsys.readouterr().err.lower()
    assert code == 2
    assert "offline" in err or "missing" in err or "players-csv" in err

    players_csv = _write_csv(db_env["tmp_path"] / "players.csv", players)
    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--sample",
            "3",
            "--seasons",
            str(SEASON),
        ]
    )
    err = capsys.readouterr().err.lower()
    assert code == 2
    assert "missing" in err or "week-csv" in err or "offline" in err

    def _raise(*_a, **_k):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(verify_data, "fetch_players", _raise)
    monkeypatch.setattr(verify_data, "fetch_week_stats", _raise)
    code = run_cli(
        [
            "--database-url",
            db_env["db_url"],
            "--sample",
            "3",
            "--seasons",
            str(SEASON),
        ]
    )
    err = capsys.readouterr().err.lower()
    assert code == 2
    assert "source" in err or "network" in err or "failed" in err


def test_offline_happy_cli_and_require_flags(db_env, monkeypatch, capsys):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)
    _block_network(monkeypatch)

    players_csv = _write_csv(db_env["tmp_path"] / "players.csv", players)
    weeks_csv = _write_csv(db_env["tmp_path"] / "weeks.csv", weeks)

    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--week-csv",
            f"{SEASON}={weeks_csv}",
            "--sample",
            str(SAMPLE),
            "--seed",
            str(SEED),
            "--seasons",
            str(SEASON),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "PASS players" in out
    assert "PASS player_week_stats" in out
    assert "identity_mismatches=0" in out
    assert "stat_mismatches=0" in out
    assert "integrity_mismatches=0" in out
    assert "filter_leaks=0" in out
    assert "total_failures=0" in out
    assert "db_rows=6" in out
    assert "UNAVAILABLE identity:" in out
    assert "UNAVAILABLE freshness:" in out
    assert "UNAVAILABLE cross_source:" in out
    assert "KNOWN_UNMAPPED" in out
    assert "RESULT PASS" in out

    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--week-csv",
            f"{SEASON}={weeks_csv}",
            "--sample",
            str(SAMPLE),
            "--seed",
            str(SEED),
            "--seasons",
            str(SEASON),
            "--require",
            "identity",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL identity:" in out
    assert "RESULT FAIL" in out

    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--week-csv",
            f"{SEASON}={weeks_csv}",
            "--sample",
            str(SAMPLE),
            "--seed",
            str(SEED),
            "--seasons",
            str(SEASON),
            "--require",
            "freshness",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL freshness:" in out
    assert "RESULT FAIL" in out


def test_csv_roundtrip_preserves_old_stat_aliases(tmp_path):
    rows = [
        _week_raw_old("00-0000001", week=1, position="QB"),
        _week_raw_new("00-0000002", week=1, position="RB"),
    ]
    reloaded = read_csv_rows(_write_csv(tmp_path / "mixed_weeks.csv", rows))
    assert len(reloaded) == len(rows)

    old_row, new_row = reloaded
    # DictWriter pads the rectangular header with "" for cells a row never
    # had; those must not resurface as present keys that shadow the populated
    # fallback aliases in map_week_row.
    assert "passing_interceptions" not in old_row
    assert "sacks_suffered" not in old_row
    assert old_row["interceptions"] == "1"
    assert old_row["sacks"] == "3"
    assert "interceptions" not in new_row
    assert "sacks" not in new_row
    assert new_row["passing_interceptions"] == "1"
    assert new_row["sacks_suffered"] == "3"

    mapped_old = map_week_row(old_row)
    mapped_new = map_week_row(new_row)
    assert mapped_old is not None
    assert mapped_new is not None
    assert mapped_old["pass_int"] == 1.0
    assert mapped_old["pass_sack"] == 3.0
    assert mapped_new["pass_int"] == 1.0
    assert mapped_new["pass_sack"] == 3.0


def test_empty_week_surface_fails_core_and_cli(db_env, monkeypatch, capsys):
    players = _fixture_players()
    _seed_from_source(db_env["factory"], players, [])
    _block_network(monkeypatch)

    with db_env["factory"]() as session:
        report = verify(
            session,
            sample_size=SAMPLE,
            seed=SEED,
            seasons=[],
            player_source_rows=players,
            week_source_rows_by_season={},
            required_checks=set(),
            max_age_hours=36.0,
            fetched_at=datetime(2026, 7, 22, tzinfo=UTC),
        )
    assert report.status == CheckStatus.FAIL
    weeks_result = _result(report, "player_week_stats")
    assert weeks_result.status == CheckStatus.FAIL
    assert weeks_result.message == "no player_week_stats seasons found"
    assert _result(report, "players").status == CheckStatus.PASS

    players_csv = _write_csv(db_env["tmp_path"] / "players.csv", players)
    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--sample",
            str(SAMPLE),
            "--seed",
            str(SEED),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL player_week_stats: no player_week_stats seasons found" in out
    assert "RESULT FAIL" in out


def test_filter_leak_exhaustive_with_clean_sample_replay(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    # Leak the rejected POST key into the DB. With SEED/SAMPLE the seeded
    # db->source draw over the 7 DB keys excludes ('00-0000001', 18), so the
    # accepted replay stays N/N while the exhaustive rejected-set/DB
    # intersection still fails the leak deterministically.
    with db_env["factory"]() as session:
        upsert_week_stats(
            session,
            SEASON,
            [
                {
                    "player_id": "00-0000001",
                    "week": 18,
                    **{column: 0.0 for column in STAT_COLUMNS},
                }
            ],
        )
        session.commit()

    report = _run_verify(db_env["factory"], players, weeks)
    assert report.status == CheckStatus.FAIL
    weeks_result = _result(report, "player_week_stats", season=SEASON)
    assert weeks_result.status == CheckStatus.FAIL
    assert ("00-0000001", 18) not in weeks_result.db_to_source_keys
    assert weeks_result.db_to_source_ok == SAMPLE
    assert weeks_result.db_to_source_total == SAMPLE
    assert weeks_result.source_to_db_ok == SAMPLE
    assert weeks_result.source_to_db_total == SAMPLE
    assert weeks_result.mismatch_count == 0
    assert weeks_result.integrity_mismatches == 0
    assert weeks_result.filter_leaks == 1
    assert weeks_result.total_failures == 1
    assert "filter_leaks=1" in weeks_result.message
    details = "\n".join(weeks_result.details)
    assert "field=filter_leak" in details
    assert "00-0000001" in details

    human = format_human_report(report)
    assert "filter_leaks=1" in human


def test_no_negative_player_rows_fail(db_env):
    players_no_neg = [row for row in _fixture_players() if row["gsis_id"] != "00-0099991"]
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players_no_neg, weeks)

    report = _run_verify(db_env["factory"], players_no_neg, weeks)
    assert report.status == CheckStatus.FAIL
    players_result = _result(report, "players")
    assert players_result.status == CheckStatus.FAIL
    assert "filter_surface_missing" in "\n".join(players_result.details)
    assert players_result.total_failures == 1
    assert _result(report, "player_week_stats", season=SEASON).status == CheckStatus.PASS


def test_no_negative_week_rows_fail(db_env):
    players = _fixture_players()
    weeks_no_neg = [row for row in _fixture_weeks() if map_week_row(row)]
    _seed_from_source(db_env["factory"], players, weeks_no_neg)

    report = _run_verify(db_env["factory"], players, weeks_no_neg)
    assert report.status == CheckStatus.FAIL
    weeks_result = _result(report, "player_week_stats", season=SEASON)
    assert weeks_result.status == CheckStatus.FAIL
    assert "filter_surface_missing" in "\n".join(weeks_result.details)
    assert weeks_result.total_failures == 1
    assert _result(report, "players").status == CheckStatus.PASS


def test_week_source_missing_season_fails(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    no_season = _week_raw_new("00-0000002", week=1, position="RB", attempts="0", completions="0")
    no_season.pop("season")
    report = _run_verify(db_env["factory"], players, weeks + [no_season])
    assert report.status == CheckStatus.FAIL
    weeks_result = _result(report, "player_week_stats", season=SEASON)
    assert "index errors" in weeks_result.message
    details = "\n".join(weeks_result.details)
    assert "field=season" in details
    assert "source=missing" in details
    assert "00-0000002" in details


def test_offline_blank_season_roundtrip_fails(db_env, monkeypatch, capsys):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)
    _block_network(monkeypatch)

    blank_season = [dict(row) for row in weeks]
    blank_season[1]["season"] = ""
    players_csv = _write_csv(db_env["tmp_path"] / "players.csv", players)
    weeks_csv = _write_csv(db_env["tmp_path"] / "weeks_blank_season.csv", blank_season)

    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--week-csv",
            f"{SEASON}={weeks_csv}",
            "--sample",
            str(SAMPLE),
            "--seed",
            str(SEED),
            "--seasons",
            str(SEASON),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "field=season" in out
    assert "source=missing" in out
    assert "00-0000002" in out
    assert "RESULT FAIL" in out


def test_week_duplicate_conflict_fail_identical_warn(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)

    conflict_weeks = weeks + [
        _week_raw_new(
            "00-0000002", week=1, position="RB", attempts="0", completions="0", rushing_yards="99"
        )
    ]
    report = _run_verify(db_env["factory"], players, conflict_weeks)
    assert report.status == CheckStatus.FAIL
    weeks_result = _result(report, "player_week_stats", season=SEASON)
    assert "index errors" in weeks_result.message
    details = "\n".join(weeks_result.details)
    assert "duplicate" in details
    assert "00-0000002" in details

    identical_weeks = weeks + [
        _week_raw_new("00-0000002", week=1, position="RB", attempts="0", completions="0")
    ]
    report = _run_verify(db_env["factory"], players, identical_weeks)
    assert report.status == CheckStatus.PASS
    warnings = "\n".join(_result(report, "player_week_stats", season=SEASON).warnings)
    assert "identical duplicate week" in warnings


def test_pure_capability_comparators():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    sampled = ["00-1", "00-2"]

    missing = compare_identity_capability(sampled, None)
    assert missing.status == CheckStatus.UNAVAILABLE
    assert "K-01/K-03" in missing.message

    empty = compare_identity_capability(sampled, [])
    assert empty.status == CheckStatus.UNAVAILABLE

    bad_cols = compare_identity_capability(
        sampled,
        [{"other": "x"}],
        columns=["other"],
    )
    assert bad_cols.status == CheckStatus.FAIL

    ok = compare_identity_capability(
        sampled,
        [{"gsis_id": "00-1"}, {"gsis_id": "00-2"}],
        columns=["gsis_id"],
    )
    assert ok.status == CheckStatus.PASS

    missing_gsis = compare_identity_capability(
        sampled,
        [{"gsis_id": "00-1"}],
        columns=["gsis_id"],
    )
    assert missing_gsis.status == CheckStatus.FAIL
    assert "00-2" in "\n".join(missing_gsis.details)

    freshness_missing = compare_freshness_capability(
        None,
        expected_players_rows=2,
        expected_week_rows_by_season={2024: 3},
        max_age_hours=36,
        now=now,
    )
    assert freshness_missing.status == CheckStatus.UNAVAILABLE
    assert "K-01" in freshness_missing.message

    bad_fresh_cols = compare_freshness_capability(
        [{"source": "x"}],
        columns=["source"],
        expected_players_rows=2,
        expected_week_rows_by_season={2024: 3},
        max_age_hours=36,
        now=now,
    )
    assert bad_fresh_cols.status == CheckStatus.FAIL

    fresh_rows = [
        {
            "source": "nflverse_players",
            "season": None,
            "rows": 2,
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "source": "nflverse_week_stats",
            "season": 2024,
            "rows": 3,
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]
    ok_fresh = compare_freshness_capability(
        fresh_rows,
        columns=["source", "season", "rows", "fetched_at"],
        expected_players_rows=2,
        expected_week_rows_by_season={2024: 3},
        max_age_hours=36,
        now=now,
    )
    assert ok_fresh.status == CheckStatus.PASS

    stale = [
        {
            "source": "nflverse_players",
            "season": None,
            "rows": 2,
            "fetched_at": (now - timedelta(hours=50)).isoformat(),
        },
        {
            "source": "nflverse_week_stats",
            "season": 2024,
            "rows": 3,
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]
    stale_result = compare_freshness_capability(
        stale,
        columns=["source", "season", "rows", "fetched_at"],
        expected_players_rows=2,
        expected_week_rows_by_season={2024: 3},
        max_age_hours=36,
        now=now,
    )
    assert stale_result.status == CheckStatus.FAIL
    assert "age_hours" in "\n".join(stale_result.details)

    future = [
        {
            "source": "nflverse_players",
            "season": None,
            "rows": 2,
            "fetched_at": (now + timedelta(hours=2)).isoformat(),
        },
        {
            "source": "nflverse_week_stats",
            "season": 2024,
            "rows": 3,
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]
    future_result = compare_freshness_capability(
        future,
        columns=["source", "season", "rows", "fetched_at"],
        expected_players_rows=2,
        expected_week_rows_by_season={2024: 3},
        max_age_hours=36,
        now=now,
    )
    assert future_result.status == CheckStatus.FAIL

    count_mismatch = [
        {
            "source": "nflverse_players",
            "season": None,
            "rows": 99,
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "source": "nflverse_week_stats",
            "season": 2024,
            "rows": 3,
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]
    count_result = compare_freshness_capability(
        count_mismatch,
        columns=["source", "season", "rows", "fetched_at"],
        expected_players_rows=2,
        expected_week_rows_by_season={2024: 3},
        max_age_hours=36,
        now=now,
    )
    assert count_result.status == CheckStatus.FAIL
    assert "field=rows" in "\n".join(count_result.details)


def test_report_json_and_human_output(db_env):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)
    report = _run_verify(db_env["factory"], players, weeks)
    payload = report.to_dict()
    encoded = json.dumps(payload)
    assert "PASS" in encoded
    assert "canonical_rows_sha256" in encoded
    assert "sample_keys" in encoded
    assert payload["sample_keys"]["players.db_to_source"]

    # DB counts are actual queried rows: 6 accepted players (K rejected) and
    # 6 accepted weeks (POST and K rejected) out of 7/8 raw fixture rows.
    sources_by_name = {source["name"]: source for source in payload["sources"]}
    assert sources_by_name["players"]["raw_row_count"] == 7
    assert sources_by_name["players"]["mapped_row_count"] == 6
    assert sources_by_name["players"]["db_row_count"] == 6
    assert sources_by_name[f"player_week_stats_{SEASON}"]["raw_row_count"] == 8
    assert sources_by_name[f"player_week_stats_{SEASON}"]["mapped_row_count"] == 6
    assert sources_by_name[f"player_week_stats_{SEASON}"]["db_row_count"] == 6
    assert payload["known_unmapped"] == [
        "return_yd,return_td,pat_made,pat_missed,fg_made,fg_missed: "
        "not source-complete (adapter zeros)"
    ]

    human = format_human_report(report)
    assert "PASS players" in human
    assert "PASS player_week_stats" in human
    assert "UNAVAILABLE identity:" in human
    assert "UNAVAILABLE freshness:" in human
    assert "UNAVAILABLE cross_source:" in human
    assert (
        "KNOWN_UNMAPPED return_yd,return_td,pat_made,pat_missed,fg_made,fg_missed: "
        "not source-complete (adapter zeros)" in human
    )
    assert "SOURCE players" in human
    assert "raw_rows=7 mapped_rows=6 db_rows=6" in human
    assert "raw_rows=8 mapped_rows=6 db_rows=6" in human
    assert "canonical_rows_sha256=" in human
    assert "RESULT PASS" in human


def test_read_only_no_ddl_or_row_changes(db_env, monkeypatch):
    players = _fixture_players()
    weeks = _fixture_weeks()
    _seed_from_source(db_env["factory"], players, weeks)
    _block_network(monkeypatch)

    players_csv = _write_csv(db_env["tmp_path"] / "players.csv", players)
    weeks_csv = _write_csv(db_env["tmp_path"] / "weeks.csv", weeks)

    with db_env["factory"]() as session:
        before_players = session.execute(sa.text("SELECT COUNT(*) FROM players")).scalar_one()
        before_weeks = session.execute(
            sa.text("SELECT COUNT(*) FROM player_week_stats")
        ).scalar_one()
        before_tables = set(sa.inspect(session.get_bind()).get_table_names())

    code = run_cli(
        [
            "--offline",
            "--database-url",
            db_env["db_url"],
            "--players-csv",
            str(players_csv),
            "--week-csv",
            f"{SEASON}={weeks_csv}",
            "--sample",
            str(SAMPLE),
            "--seed",
            str(SEED),
            "--seasons",
            str(SEASON),
        ]
    )
    assert code == 0

    with db_env["factory"]() as session:
        after_players = session.execute(sa.text("SELECT COUNT(*) FROM players")).scalar_one()
        after_weeks = session.execute(
            sa.text("SELECT COUNT(*) FROM player_week_stats")
        ).scalar_one()
        after_tables = set(sa.inspect(session.get_bind()).get_table_names())

    assert before_players == after_players
    assert before_weeks == after_weeks
    assert before_tables == after_tables
    assert "player_ids" not in after_tables
    assert "source_syncs" not in after_tables


def test_missing_database_file_exits_2(tmp_path, monkeypatch):
    _block_network(monkeypatch)
    missing = tmp_path / "nope.db"
    code = run_cli(["--database-url", f"sqlite:///{missing}", "--sample", "1"])
    assert code == 2


def test_main_raises_system_exit(monkeypatch):
    monkeypatch.setattr(verify_data, "run_cli", lambda argv=None: 0)
    with pytest.raises(SystemExit) as exc:
        verify_data.main()
    assert exc.value.code == 0
