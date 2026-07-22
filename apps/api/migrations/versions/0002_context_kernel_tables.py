"""context kernel and Milestone Zero data vessels

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:  # noqa: PLR0915
    op.create_table(
        "source_syncs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.Text(), nullable=False),
        sa.CheckConstraint("rows >= 0", name="ck_source_syncs_rows_nonnegative"),
    )
    op.create_index(
        "uq_source_syncs_global_source",
        "source_syncs",
        ["source"],
        unique=True,
        sqlite_where=sa.text("season IS NULL"),
    )
    op.create_index(
        "uq_source_syncs_seasonal_source",
        "source_syncs",
        ["source", "season"],
        unique=True,
        sqlite_where=sa.text("season IS NOT NULL"),
    )
    op.create_index("ix_source_syncs_fetched_at", "source_syncs", ["fetched_at"])

    op.create_table(
        "player_ids",
        sa.Column("gsis_id", sa.Text(), primary_key=True),
        sa.Column("sleeper_id", sa.Text(), nullable=True),
        sa.Column("espn_id", sa.Text(), nullable=True),
        sa.Column("pfr_id", sa.Text(), nullable=True),
        sa.Column("cfb_player_id", sa.Text(), nullable=True),
        sa.Column("mfl_id", sa.Text(), nullable=True),
        sa.Column("fantasycalc_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("merge_name", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("team", sa.Text(), nullable=True),
    )
    for column in ("sleeper_id", "espn_id", "pfr_id", "cfb_player_id", "fantasycalc_id"):
        op.create_index(
            f"uq_player_ids_{column}",
            "player_ids",
            [column],
            unique=True,
            sqlite_where=sa.text(f"{column} IS NOT NULL"),
        )
    op.create_index("ix_player_ids_merge_name", "player_ids", ["merge_name"])

    op.create_table(
        "player_meta",
        sa.Column(
            "gsis_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("birth_date", sa.Text(), nullable=True),
        sa.Column("height_in", sa.Integer(), nullable=True),
        sa.Column("weight_lb", sa.Integer(), nullable=True),
        sa.Column("college", sa.Text(), nullable=True),
        sa.Column("years_exp", sa.Integer(), nullable=True),
        sa.Column("jersey_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("headshot_url", sa.Text(), nullable=True),
        sa.Column("as_of_season", sa.Integer(), nullable=True),
        sa.Column("as_of_week", sa.Integer(), nullable=True),
    )

    op.create_table(
        "leagues",
        sa.Column("league_id", sa.Text(), primary_key=True),
        sa.Column("sleeper_user_id", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("sport", sa.Text(), nullable=False, server_default=sa.text("'nfl'")),
        sa.Column("total_rosters", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("ix_leagues_username", "leagues", ["username"])
    op.create_index("ix_leagues_sleeper_user_id", "leagues", ["sleeper_user_id"])

    op.create_table(
        "context_revisions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "league_id",
            sa.Text(),
            sa.ForeignKey("leagues.league_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("compiled_rules_json", sa.Text(), nullable=False),
        sa.Column("coverage_json", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "league_id",
            "revision",
            name="uq_context_revisions_league_revision",
        ),
    )
    op.create_index(
        "ix_context_revisions_league_created_at",
        "context_revisions",
        ["league_id", "created_at"],
    )

    op.create_table(
        "scenarios",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "base_revision_id",
            sa.Text(),
            sa.ForeignKey("context_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('trade', 'injury_out', 'lineup_change', 'waiver')",
            name="ck_scenarios_kind",
        ),
    )
    op.create_index("ix_scenarios_base_revision_id", "scenarios", ["base_revision_id"])

    op.create_table(
        "games",
        sa.Column("game_id", sa.Text(), primary_key=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("game_type", sa.Text(), nullable=False),
        sa.Column("gameday", sa.Text(), nullable=False),
        sa.Column("away_team", sa.Text(), nullable=False),
        sa.Column("home_team", sa.Text(), nullable=False),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("result", sa.Integer(), nullable=True),
        sa.Column("total", sa.Float(), nullable=True),
        sa.Column("overtime", sa.Integer(), nullable=True),
        sa.Column("away_rest", sa.Integer(), nullable=True),
        sa.Column("home_rest", sa.Integer(), nullable=True),
        sa.Column("spread_line", sa.Float(), nullable=True),
        sa.Column("total_line", sa.Float(), nullable=True),
        sa.Column("away_moneyline", sa.Float(), nullable=True),
        sa.Column("home_moneyline", sa.Float(), nullable=True),
        sa.Column("roof", sa.Text(), nullable=True),
        sa.Column("surface", sa.Text(), nullable=True),
    )
    op.create_index("ix_games_season_week", "games", ["season", "week"])
    op.create_index("ix_games_home_team_season", "games", ["home_team", "season"])
    op.create_index("ix_games_away_team_season", "games", ["away_team", "season"])

    op.create_table(
        "snap_counts",
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("week", sa.Integer(), primary_key=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("opponent", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("offense_snaps", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("offense_pct", sa.Float(), nullable=True),
        sa.Column("defense_snaps", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("defense_pct", sa.Float(), nullable=True),
        sa.Column("st_snaps", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("st_pct", sa.Float(), nullable=True),
    )
    op.create_index("ix_snap_counts_season_week", "snap_counts", ["season", "week"])

    op.create_table(
        "injuries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("report_status", sa.Text(), nullable=True),
        sa.Column("practice_status", sa.Text(), nullable=True),
        sa.Column("report_primary_injury", sa.Text(), nullable=True),
        sa.Column("practice_primary_injury", sa.Text(), nullable=True),
        sa.Column("date_modified", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "player_id",
            "season",
            "week",
            "report_primary_injury",
            name="uq_injuries_player_week_injury",
        ),
    )
    op.create_index("ix_injuries_season_week", "injuries", ["season", "week"])
    op.create_index("ix_injuries_report_status", "injuries", ["report_status"])

    op.create_table(
        "depth_charts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("team", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("depth_position", sa.Text(), nullable=True),
        sa.Column("depth_team", sa.Integer(), nullable=True),
        sa.Column("formation", sa.Text(), nullable=True),
        sa.Column("jersey_number", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "player_id",
            "season",
            "week",
            "formation",
            "depth_position",
            name="uq_depth_charts_player_week_slot",
        ),
    )
    op.create_index(
        "ix_depth_charts_team_season_week",
        "depth_charts",
        ["team", "season", "week"],
    )

    op.create_table(
        "ngs_week_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("season_type", sa.Text(), nullable=False),
        sa.Column("stat_type", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("avg_time_to_throw", sa.Float(), nullable=True),
        sa.Column("avg_intended_air_yards", sa.Float(), nullable=True),
        sa.Column("avg_separation", sa.Float(), nullable=True),
        sa.Column("avg_yac_above_expectation", sa.Float(), nullable=True),
        sa.Column("completion_percentage_above_expectation", sa.Float(), nullable=True),
        sa.Column("aggressiveness", sa.Float(), nullable=True),
        sa.Column("rush_yards_over_expected", sa.Float(), nullable=True),
        sa.Column("rush_yards_over_expected_per_att", sa.Float(), nullable=True),
        sa.Column("efficiency", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "stat_type IN ('passing', 'receiving', 'rushing')",
            name="ck_ngs_week_stats_stat_type",
        ),
        sa.UniqueConstraint(
            "player_id",
            "season",
            "week",
            "season_type",
            "stat_type",
            name="uq_ngs_week_stats_natural_key",
        ),
    )

    op.create_table(
        "pfr_week_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id"),
            nullable=False,
        ),
        sa.Column("pfr_player_id", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("game_type", sa.Text(), nullable=False),
        sa.Column("stat_type", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("opponent", sa.Text(), nullable=True),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("hurry", sa.Float(), nullable=True),
        sa.Column("hit", sa.Float(), nullable=True),
        sa.Column("blitz", sa.Float(), nullable=True),
        sa.Column("bad_throw", sa.Float(), nullable=True),
        sa.Column("drops", sa.Float(), nullable=True),
        sa.Column("receiving_drop", sa.Float(), nullable=True),
        sa.Column("rush_broken_tackles", sa.Float(), nullable=True),
        sa.Column("rec_broken_tackles", sa.Float(), nullable=True),
        sa.Column("rush_yards_before_contact", sa.Float(), nullable=True),
        sa.Column("rush_yards_after_contact", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "stat_type IN ('pass', 'rush', 'rec', 'def')",
            name="ck_pfr_week_stats_stat_type",
        ),
        sa.UniqueConstraint(
            "pfr_player_id",
            "season",
            "week",
            "game_type",
            "stat_type",
            name="uq_pfr_week_stats_natural_key",
        ),
    )
    op.create_index(
        "ix_pfr_week_stats_player_season",
        "pfr_week_stats",
        ["player_id", "season"],
    )

    op.create_table(
        "ftn_week_stats",
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id"),
            primary_key=True,
        ),
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("week", sa.Integer(), primary_key=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("plays", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("play_action", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("screen", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("motion", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("no_huddle", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rpo", sa.Float(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "qbr_week_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id"),
            nullable=False,
        ),
        sa.Column("espn_player_id", sa.Text(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("season_type", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("qbr_total", sa.Float(), nullable=True),
        sa.Column("qbr_raw", sa.Float(), nullable=True),
        sa.Column("pts_added", sa.Float(), nullable=True),
        sa.Column("qb_plays", sa.Float(), nullable=True),
        sa.Column("epa_total", sa.Float(), nullable=True),
        sa.Column("qualified", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "espn_player_id",
            "season",
            "week",
            "season_type",
            name="uq_qbr_week_stats_natural_key",
        ),
    )
    op.create_index(
        "ix_qbr_week_stats_player_season",
        "qbr_week_stats",
        ["player_id", "season"],
    )

    op.create_table(
        "contracts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("otc_id", sa.Text(), nullable=True),
        sa.Column(
            "player_id",
            sa.Text(),
            sa.ForeignKey("players.gsis_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("year_signed", sa.Integer(), nullable=True),
        sa.Column("years", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("apy", sa.Float(), nullable=True),
        sa.Column("guaranteed", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("player_page", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_contracts_otc_id",
        "contracts",
        ["otc_id"],
        unique=True,
        sqlite_where=sa.text("otc_id IS NOT NULL"),
    )
    op.create_index("ix_contracts_player_id", "contracts", ["player_id"])
    op.create_index("ix_contracts_team_year_signed", "contracts", ["team", "year_signed"])

    op.create_table(
        "draft_picks",
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("round", sa.Integer(), primary_key=True),
        sa.Column("pick", sa.Integer(), primary_key=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("gsis_id", sa.Text(), nullable=True),
        sa.Column("pfr_player_id", sa.Text(), nullable=True),
        sa.Column("cfb_player_id", sa.Text(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("college", sa.Text(), nullable=True),
        sa.Column("age", sa.Float(), nullable=True),
    )
    op.create_index("ix_draft_picks_gsis_id", "draft_picks", ["gsis_id"])
    op.create_index("ix_draft_picks_pfr_player_id", "draft_picks", ["pfr_player_id"])
    op.create_index("ix_draft_picks_cfb_player_id", "draft_picks", ["cfb_player_id"])
    op.create_index("ix_draft_picks_college", "draft_picks", ["college"])

    op.create_table(
        "combine",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("draft_year", sa.Integer(), nullable=False),
        sa.Column("pfr_id", sa.Text(), nullable=True),
        sa.Column("cfb_id", sa.Text(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=False),
        sa.Column("school", sa.Text(), nullable=True),
        sa.Column("height_in", sa.Float(), nullable=True),
        sa.Column("weight_lb", sa.Float(), nullable=True),
        sa.Column("forty", sa.Float(), nullable=True),
        sa.Column("bench", sa.Float(), nullable=True),
        sa.Column("vertical", sa.Float(), nullable=True),
        sa.Column("broad_jump", sa.Float(), nullable=True),
        sa.Column("cone", sa.Float(), nullable=True),
        sa.Column("shuttle", sa.Float(), nullable=True),
        sa.UniqueConstraint(
            "player_name",
            "draft_year",
            "position",
            name="uq_combine_player_draft_position",
        ),
    )
    op.create_index("ix_combine_pfr_id", "combine", ["pfr_id"])
    op.create_index("ix_combine_cfb_id", "combine", ["cfb_id"])
    op.create_index("ix_combine_draft_year", "combine", ["draft_year"])

    op.create_table(
        "market_values",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("player_id", sa.Text(), nullable=True),
        sa.Column("sleeper_id", sa.Text(), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "source IN ('fantasycalc', 'dynastyprocess')",
            name="ck_market_values_source",
        ),
    )
    op.create_index(
        "uq_market_values_player",
        "market_values",
        ["source", "format", "player_id"],
        unique=True,
        sqlite_where=sa.text("player_id IS NOT NULL"),
    )
    op.create_index(
        "uq_market_values_sleeper",
        "market_values",
        ["source", "format", "sleeper_id"],
        unique=True,
        sqlite_where=sa.text("sleeper_id IS NOT NULL"),
    )
    op.create_index("ix_market_values_fetched_at", "market_values", ["fetched_at"])

    op.create_table(
        "college_season_stats",
        sa.Column("cfb_player_id", sa.Text(), primary_key=True),
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("conference", sa.Text(), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("games", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_att", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_cmp", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_yd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_td", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_int", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rush_att", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rush_yd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rush_td", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("target", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rec", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rec_yd", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rec_td", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("fumble", sa.Float(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "ix_college_season_stats_season_position",
        "college_season_stats",
        ["season", "position"],
    )
    op.create_index(
        "ix_college_season_stats_player_name",
        "college_season_stats",
        ["player_name"],
    )


def downgrade() -> None:  # noqa: PLR0915
    op.drop_index(
        "ix_college_season_stats_player_name",
        table_name="college_season_stats",
    )
    op.drop_index(
        "ix_college_season_stats_season_position",
        table_name="college_season_stats",
    )
    op.drop_table("college_season_stats")

    op.drop_index("ix_market_values_fetched_at", table_name="market_values")
    op.drop_index("uq_market_values_sleeper", table_name="market_values")
    op.drop_index("uq_market_values_player", table_name="market_values")
    op.drop_table("market_values")

    op.drop_index("ix_combine_draft_year", table_name="combine")
    op.drop_index("ix_combine_cfb_id", table_name="combine")
    op.drop_index("ix_combine_pfr_id", table_name="combine")
    op.drop_table("combine")

    op.drop_index("ix_draft_picks_college", table_name="draft_picks")
    op.drop_index("ix_draft_picks_cfb_player_id", table_name="draft_picks")
    op.drop_index("ix_draft_picks_pfr_player_id", table_name="draft_picks")
    op.drop_index("ix_draft_picks_gsis_id", table_name="draft_picks")
    op.drop_table("draft_picks")

    op.drop_index("ix_contracts_team_year_signed", table_name="contracts")
    op.drop_index("ix_contracts_player_id", table_name="contracts")
    op.drop_index("uq_contracts_otc_id", table_name="contracts")
    op.drop_table("contracts")

    op.drop_index("ix_qbr_week_stats_player_season", table_name="qbr_week_stats")
    op.drop_table("qbr_week_stats")

    op.drop_table("ftn_week_stats")

    op.drop_index("ix_pfr_week_stats_player_season", table_name="pfr_week_stats")
    op.drop_table("pfr_week_stats")

    op.drop_table("ngs_week_stats")

    op.drop_index(
        "ix_depth_charts_team_season_week",
        table_name="depth_charts",
    )
    op.drop_table("depth_charts")

    op.drop_index("ix_injuries_report_status", table_name="injuries")
    op.drop_index("ix_injuries_season_week", table_name="injuries")
    op.drop_table("injuries")

    op.drop_index("ix_snap_counts_season_week", table_name="snap_counts")
    op.drop_table("snap_counts")

    op.drop_index("ix_games_away_team_season", table_name="games")
    op.drop_index("ix_games_home_team_season", table_name="games")
    op.drop_index("ix_games_season_week", table_name="games")
    op.drop_table("games")

    op.drop_index("ix_scenarios_base_revision_id", table_name="scenarios")
    op.drop_table("scenarios")

    op.drop_index(
        "ix_context_revisions_league_created_at",
        table_name="context_revisions",
    )
    op.drop_table("context_revisions")

    op.drop_index("ix_leagues_sleeper_user_id", table_name="leagues")
    op.drop_index("ix_leagues_username", table_name="leagues")
    op.drop_table("leagues")

    op.drop_table("player_meta")

    op.drop_index("ix_player_ids_merge_name", table_name="player_ids")
    for column in reversed(("sleeper_id", "espn_id", "pfr_id", "cfb_player_id", "fantasycalc_id")):
        op.drop_index(f"uq_player_ids_{column}", table_name="player_ids")
    op.drop_table("player_ids")

    op.drop_index("ix_source_syncs_fetched_at", table_name="source_syncs")
    op.drop_index("uq_source_syncs_seasonal_source", table_name="source_syncs")
    op.drop_index("uq_source_syncs_global_source", table_name="source_syncs")
    op.drop_table("source_syncs")
