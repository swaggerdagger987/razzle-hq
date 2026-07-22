from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine.reflection import Inspector

from razzle_api.config import get_settings
from razzle_api.ingest.nflverse import STAT_COLUMNS

API_DIR = Path(__file__).resolve().parents[2]

CANONICAL_TABLES = {
    "college_season_stats",
    "combine",
    "context_revisions",
    "contracts",
    "depth_charts",
    "draft_picks",
    "ftn_week_stats",
    "games",
    "injuries",
    "leagues",
    "market_values",
    "ngs_week_stats",
    "pfr_week_stats",
    "player_ids",
    "player_meta",
    "player_week_stats",
    "players",
    "qbr_week_stats",
    "scenarios",
    "snap_counts",
    "source_syncs",
}

EXPECTED_COLUMNS = {
    "players": {"gsis_id", "name", "position", "team", "sleeper_id"},
    "player_week_stats": {"id", "player_id", "season", "week", *STAT_COLUMNS},
    "source_syncs": {"id", "source", "season", "rows", "fetched_at"},
    "player_ids": {
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
    },
    "player_meta": {
        "gsis_id",
        "birth_date",
        "height_in",
        "weight_lb",
        "college",
        "years_exp",
        "jersey_number",
        "status",
        "headshot_url",
        "as_of_season",
        "as_of_week",
    },
    "leagues": {
        "league_id",
        "sleeper_user_id",
        "username",
        "name",
        "season",
        "sport",
        "total_rosters",
        "created_at",
        "updated_at",
    },
    "context_revisions": {
        "id",
        "league_id",
        "revision",
        "compiled_rules_json",
        "coverage_json",
        "snapshot_json",
        "sources_json",
        "created_at",
    },
    "scenarios": {
        "id",
        "base_revision_id",
        "kind",
        "payload_json",
        "label",
        "created_at",
    },
    "games": {
        "game_id",
        "season",
        "week",
        "game_type",
        "gameday",
        "away_team",
        "home_team",
        "away_score",
        "home_score",
        "result",
        "total",
        "overtime",
        "away_rest",
        "home_rest",
        "spread_line",
        "total_line",
        "away_moneyline",
        "home_moneyline",
        "roof",
        "surface",
    },
    "snap_counts": {
        "player_id",
        "season",
        "week",
        "team",
        "opponent",
        "position",
        "offense_snaps",
        "offense_pct",
        "defense_snaps",
        "defense_pct",
        "st_snaps",
        "st_pct",
    },
    "injuries": {
        "id",
        "player_id",
        "season",
        "week",
        "team",
        "position",
        "report_status",
        "practice_status",
        "report_primary_injury",
        "practice_primary_injury",
        "date_modified",
    },
    "depth_charts": {
        "id",
        "player_id",
        "season",
        "week",
        "team",
        "position",
        "depth_position",
        "depth_team",
        "formation",
        "jersey_number",
    },
    "ngs_week_stats": {
        "id",
        "player_id",
        "season",
        "week",
        "season_type",
        "stat_type",
        "team",
        "position",
        "avg_time_to_throw",
        "avg_intended_air_yards",
        "avg_separation",
        "avg_yac_above_expectation",
        "completion_percentage_above_expectation",
        "aggressiveness",
        "rush_yards_over_expected",
        "rush_yards_over_expected_per_att",
        "efficiency",
    },
    "pfr_week_stats": {
        "id",
        "player_id",
        "pfr_player_id",
        "season",
        "week",
        "game_type",
        "stat_type",
        "team",
        "opponent",
        "pressure",
        "hurry",
        "hit",
        "blitz",
        "bad_throw",
        "drops",
        "receiving_drop",
        "rush_broken_tackles",
        "rec_broken_tackles",
        "rush_yards_before_contact",
        "rush_yards_after_contact",
    },
    "ftn_week_stats": {
        "player_id",
        "season",
        "week",
        "team",
        "plays",
        "play_action",
        "screen",
        "motion",
        "no_huddle",
        "rpo",
    },
    "qbr_week_stats": {
        "id",
        "player_id",
        "espn_player_id",
        "season",
        "week",
        "season_type",
        "team",
        "qbr_total",
        "qbr_raw",
        "pts_added",
        "qb_plays",
        "epa_total",
        "qualified",
    },
    "contracts": {
        "id",
        "otc_id",
        "player_id",
        "player_name",
        "position",
        "team",
        "year_signed",
        "years",
        "value",
        "apy",
        "guaranteed",
        "is_active",
        "player_page",
    },
    "draft_picks": {
        "season",
        "round",
        "pick",
        "team",
        "gsis_id",
        "pfr_player_id",
        "cfb_player_id",
        "player_name",
        "position",
        "category",
        "college",
        "age",
    },
    "combine": {
        "id",
        "season",
        "draft_year",
        "pfr_id",
        "cfb_id",
        "player_name",
        "position",
        "school",
        "height_in",
        "weight_lb",
        "forty",
        "bench",
        "vertical",
        "broad_jump",
        "cone",
        "shuttle",
    },
    "market_values": {
        "id",
        "source",
        "format",
        "player_id",
        "sleeper_id",
        "value",
        "fetched_at",
    },
    "college_season_stats": {
        "cfb_player_id",
        "season",
        "player_name",
        "team",
        "conference",
        "position",
        "games",
        "pass_att",
        "pass_cmp",
        "pass_yd",
        "pass_td",
        "pass_int",
        "rush_att",
        "rush_yd",
        "rush_td",
        "target",
        "rec",
        "rec_yd",
        "rec_td",
        "fumble",
    },
}

EXPECTED_PRIMARY_KEYS = {
    "players": ("gsis_id",),
    "player_week_stats": ("id",),
    "source_syncs": ("id",),
    "player_ids": ("gsis_id",),
    "player_meta": ("gsis_id",),
    "leagues": ("league_id",),
    "context_revisions": ("id",),
    "scenarios": ("id",),
    "games": ("game_id",),
    "snap_counts": ("player_id", "season", "week"),
    "injuries": ("id",),
    "depth_charts": ("id",),
    "ngs_week_stats": ("id",),
    "pfr_week_stats": ("id",),
    "ftn_week_stats": ("player_id", "season", "week"),
    "qbr_week_stats": ("id",),
    "contracts": ("id",),
    "draft_picks": ("season", "round", "pick"),
    "combine": ("id",),
    "market_values": ("id",),
    "college_season_stats": ("cfb_player_id", "season"),
}


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _configured_database(tmp_path, monkeypatch, name: str = "razzle.db") -> tuple[str, Config]:
    db_url = f"sqlite:///{tmp_path / name}"
    monkeypatch.setenv("RAZZLE_DATABASE_URL", db_url)
    get_settings.cache_clear()
    return db_url, _alembic_config(db_url)


def _column_names(inspector: Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def test_upgrade_head_creates_exact_canonical_schema(tmp_path, monkeypatch):
    db_url, cfg = _configured_database(tmp_path, monkeypatch)
    try:
        command.upgrade(cfg, "head")

        engine = sa.create_engine(db_url)
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names()) - {"alembic_version"}
        assert tables == CANONICAL_TABLES
        assert len(tables) == 21

        assert set(EXPECTED_COLUMNS) == CANONICAL_TABLES
        for table, expected in EXPECTED_COLUMNS.items():
            assert _column_names(inspector, table) == expected
        for table, expected in EXPECTED_PRIMARY_KEYS.items():
            assert tuple(inspector.get_pk_constraint(table)["constrained_columns"]) == expected
        assert "updated_at" not in _column_names(inspector, "context_revisions")
        engine.dispose()

        command.downgrade(cfg, "base")
        engine = sa.create_engine(db_url)
        remaining = set(sa.inspect(engine).get_table_names()) - {"alembic_version"}
        assert remaining == set()
        engine.dispose()
    finally:
        get_settings.cache_clear()


def test_0001_rows_and_schema_survive_0002_roundtrip(tmp_path, monkeypatch):
    db_url, cfg = _configured_database(tmp_path, monkeypatch, "roundtrip.db")
    try:
        command.upgrade(cfg, "0001")
        engine = sa.create_engine(db_url)
        before_inspector = sa.inspect(engine)
        players_columns = _column_names(before_inspector, "players")
        week_columns = _column_names(before_inspector, "player_week_stats")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO players (gsis_id, name, position, team, sleeper_id) "
                    "VALUES ('00-0000001', 'Round Trip', 'QB', 'BUF', 'sleeper-1')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO player_week_stats "
                    "(player_id, season, week, pass_att, pass_yd, pass_td) "
                    "VALUES ('00-0000001', 2025, 1, 30, 250, 2)"
                )
            )
        with engine.connect() as connection:
            player_before = dict(
                connection.execute(sa.text("SELECT * FROM players")).mappings().one()
            )
            week_before = dict(
                connection.execute(sa.text("SELECT * FROM player_week_stats")).mappings().one()
            )
        engine.dispose()

        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        assert _column_names(sa.inspect(engine), "players") == players_columns
        assert _column_names(sa.inspect(engine), "player_week_stats") == week_columns
        engine.dispose()

        command.downgrade(cfg, "0001")
        engine = sa.create_engine(db_url)
        assert (set(sa.inspect(engine).get_table_names()) - {"alembic_version"}) == {
            "players",
            "player_week_stats",
        }
        with engine.connect() as connection:
            assert dict(connection.execute(sa.text("SELECT * FROM players")).mappings().one()) == (
                player_before
            )
            assert (
                dict(
                    connection.execute(sa.text("SELECT * FROM player_week_stats")).mappings().one()
                )
                == week_before
            )
        engine.dispose()

        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        with engine.connect() as connection:
            assert dict(connection.execute(sa.text("SELECT * FROM players")).mappings().one()) == (
                player_before
            )
            assert (
                dict(
                    connection.execute(sa.text("SELECT * FROM player_week_stats")).mappings().one()
                )
                == week_before
            )
        assert (set(sa.inspect(engine).get_table_names()) - {"alembic_version"}) == CANONICAL_TABLES
        engine.dispose()
    finally:
        get_settings.cache_clear()


def test_source_sync_partial_uniqueness_and_orphan_player_ids(tmp_path, monkeypatch):
    db_url, cfg = _configured_database(tmp_path, monkeypatch, "constraints.db")
    try:
        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.execute(
                sa.text(
                    "INSERT INTO source_syncs (source, season, rows, fetched_at) VALUES "
                    "('nflverse_players', NULL, 2, '2026-07-22T12:00:00+00:00'),"
                    "('nflverse_week_stats', 2024, 3, '2026-07-22T12:00:00+00:00'),"
                    "('nflverse_week_stats', 2025, 4, '2026-07-22T12:00:00+00:00')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO player_ids (gsis_id, name) "
                    "VALUES ('orphan-crosswalk-id', 'Crosswalk Only')"
                )
            )

        invalid_statements = (
            "INSERT INTO source_syncs (source, season, rows, fetched_at) "
            "VALUES ('nflverse_players', NULL, 9, '2026-07-22T13:00:00+00:00')",
            "INSERT INTO source_syncs (source, season, rows, fetched_at) "
            "VALUES ('nflverse_week_stats', 2024, 9, '2026-07-22T13:00:00+00:00')",
            "INSERT INTO source_syncs (source, season, rows, fetched_at) "
            "VALUES ('bad-count', NULL, -1, '2026-07-22T13:00:00+00:00')",
        )
        for statement in invalid_statements:
            with pytest.raises(sa.exc.IntegrityError):
                with engine.begin() as connection:
                    connection.execute(sa.text(statement))

        with engine.connect() as connection:
            assert (
                connection.execute(sa.text("SELECT COUNT(*) FROM source_syncs")).scalar_one() == 3
            )
            orphan_count = connection.execute(
                sa.text("SELECT COUNT(*) FROM player_ids WHERE gsis_id = 'orphan-crosswalk-id'")
            ).scalar_one()
            assert orphan_count == 1
        engine.dispose()
    finally:
        get_settings.cache_clear()


def test_scenario_check_and_context_cascade(tmp_path, monkeypatch):
    db_url, cfg = _configured_database(tmp_path, monkeypatch, "context.db")
    try:
        command.upgrade(cfg, "head")
        engine = sa.create_engine(db_url)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.execute(
                sa.text(
                    "INSERT INTO leagues "
                    "(league_id, sleeper_user_id, username, name, season, created_at, updated_at) "
                    "VALUES "
                    "('league-1', 'user-1', 'razzle', 'Test League', 2026, "
                    "'2026-07-22T12:00:00+00:00', '2026-07-22T12:00:00+00:00')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO context_revisions "
                    "(id, league_id, revision, compiled_rules_json, coverage_json, "
                    "snapshot_json, sources_json, created_at) VALUES "
                    "('revision-1', 'league-1', 1, '{}', '{}', '{}', '[]', "
                    "'2026-07-22T12:00:00+00:00')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO scenarios "
                    "(id, base_revision_id, kind, payload_json, created_at) VALUES "
                    "('scenario-1', 'revision-1', 'trade', '{}', "
                    "'2026-07-22T12:00:00+00:00')"
                )
            )

        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.execute(
                    sa.text(
                        "INSERT INTO scenarios "
                        "(id, base_revision_id, kind, payload_json, created_at) VALUES "
                        "('bad-scenario', 'revision-1', 'forecast', '{}', "
                        "'2026-07-22T12:00:00+00:00')"
                    )
                )

        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.execute(sa.text("DELETE FROM leagues WHERE league_id = 'league-1'"))

        with engine.connect() as connection:
            revisions = connection.execute(
                sa.text("SELECT COUNT(*) FROM context_revisions")
            ).scalar_one()
            scenarios = connection.execute(sa.text("SELECT COUNT(*) FROM scenarios")).scalar_one()
            assert revisions == 0
            assert scenarios == 0
        engine.dispose()
    finally:
        get_settings.cache_clear()
