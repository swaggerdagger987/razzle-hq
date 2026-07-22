from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from razzle_api.domain.scoring import compile_league
from razzle_api.domain.scoring.compiler import (
    CompiledRules,
    CoverageReport,
    MatchupFormat,
    TiebreakerConfig,
    UnsupportedScoringKey,
)
from razzle_api.domain.scoring.config import RangeRule, YardageBonus
from razzle_api.domain.scoring.engine import PlayerWeekStats, score_week

_CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"
_COMPILER_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "razzle_api"
    / "domain"
    / "scoring"
    / "compiler.py"
)


def _load_cassette(name: str) -> dict[str, Any]:
    return json.loads((_CASSETTES / name).read_text())


def _base_league(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "league_id": "test-league",
        "name": "Test League",
        "season": "2025",
        "total_rosters": 12,
        "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"],
        "scoring_settings": {},
        "settings": {"type": 0},
    }
    payload.update(overrides)
    return payload


def test_cassette_tep_median_dynasty_full_golden() -> None:
    compiled = compile_league(_load_cassette("sleeper_league_tep_median_dynasty.json"))

    assert compiled.league_id == "202501010000000001"
    assert compiled.name == "Razzle Dynasty TEP Median"
    assert compiled.season == "2025"
    assert compiled.coverage.status == "full"
    assert compiled.coverage.unsupported_keys == []
    assert compiled.coverage.ignored_zero_keys == []
    assert compiled.matchup == MatchupFormat(style="h2h_median", median_enabled=True)
    assert compiled.league.format == "dynasty"
    assert compiled.te_premium is True
    assert compiled.superflex is True
    assert compiled.best_ball is False
    assert compiled.league.scoring.receiving.te_premium == 0.5
    assert compiled.league.scoring.receiving.rec == 1.0
    assert compiled.league.roster.superflex == 1
    assert compiled.league.roster.qb == 1
    assert compiled.league.roster.dst == 1
    assert compiled.league.roster.k == 1
    assert compiled.league.roster.taxi == 3
    assert compiled.league.league_size == 12
    assert compiled.league.waiver_type == "faab"
    assert compiled.league.faab_budget == 200
    assert compiled.league.trade_deadline_week == 11
    assert compiled.league.playoff_teams == 6
    assert compiled.league.playoff_start_week == 15
    assert compiled.tiebreakers == TiebreakerConfig(
        order=["record", "points_for", "points_against"],
        playoff_seed_type=0,
    )
    assert compiled.league.scoring.passing.pass_yardage_bonuses == [
        YardageBonus(threshold=300.0, points=3.0),
        YardageBonus(threshold=400.0, points=2.0),
    ]
    assert compiled.league.scoring.kicking.fg_made_ranges == [
        RangeRule(min_value=0.0, max_value=19.0, points=3.0),
        RangeRule(min_value=20.0, max_value=29.0, points=3.0),
        RangeRule(min_value=30.0, max_value=39.0, points=3.0),
        RangeRule(min_value=40.0, max_value=49.0, points=4.0),
        RangeRule(min_value=50.0, max_value=None, points=5.0),
    ]
    assert compiled.league.scoring.defense.points_allowed_ranges[0] == RangeRule(
        min_value=0.0, max_value=0.0, points=10.0
    )
    assert compiled.league.scoring.defense.interception == 2.0
    assert compiled.league.scoring.passing.pass_int == -2.0
    assert "bonus_rec_te" in compiled.coverage.supported_keys
    assert "bonus_pass_yd_300" in compiled.coverage.supported_keys
    assert "int" in compiled.coverage.supported_keys
    assert "pass_int" in compiled.coverage.supported_keys


def test_cassette_standard_redraft_full_golden() -> None:
    compiled = compile_league(_load_cassette("sleeper_league_standard_redraft.json"))

    assert compiled.league_id == "202501010000000002"
    assert compiled.name == "Razzle Standard Redraft"
    assert compiled.season == "2025"
    assert compiled.coverage.status == "full"
    assert compiled.coverage.unsupported_keys == []
    assert compiled.matchup == MatchupFormat(style="h2h", median_enabled=False)
    assert compiled.league.format == "redraft"
    assert compiled.te_premium is False
    assert compiled.superflex is False
    assert compiled.best_ball is False
    assert compiled.league.scoring.receiving.rec == 0.0
    assert compiled.league.roster.superflex == 0
    assert compiled.league.roster.k == 1
    assert compiled.league.roster.dst == 1
    assert compiled.league.roster.taxi == 0
    assert compiled.league.waiver_type == "rolling"
    assert compiled.league.trade_deadline_week == 10
    assert compiled.tiebreakers.playoff_seed_type == 1
    assert compiled.league.scoring.defense.fumble_recovery == 2.0


def test_unsupported_nonzero_is_partial_and_supported_fields_compile() -> None:
    compiled = compile_league(
        _base_league(
            scoring_settings={
                "rec": 1.0,
                "pass_td": 6.0,
                "bonus_pass_cmp_25": 2.0,
            }
        )
    )

    assert compiled.coverage.status == "partial"
    assert compiled.league.scoring.receiving.rec == 1.0
    assert compiled.league.scoring.passing.pass_td == 6.0
    assert compiled.coverage.supported_keys == ["pass_td", "rec"]
    assert compiled.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="bonus_pass_cmp_25", value=2.0, reason="unmapped")
    ]
    assert compiled.coverage.ignored_zero_keys == []


def test_unsupported_zero_is_ignored_and_stays_full() -> None:
    compiled = compile_league(
        _base_league(
            scoring_settings={
                "rec": 0.5,
                "bonus_pass_cmp_25": 0.0,
                "return_yd": 0.0,
            }
        )
    )

    assert compiled.coverage.status == "full"
    assert compiled.league.scoring.receiving.rec == 0.5
    assert compiled.coverage.supported_keys == ["rec"]
    assert compiled.coverage.unsupported_keys == []
    assert compiled.coverage.ignored_zero_keys == ["bonus_pass_cmp_25", "return_yd"]


def test_return_yard_nonzero_stays_unsupported_partial() -> None:
    compiled = compile_league(_base_league(scoring_settings={"return_yd": 0.1}))

    assert compiled.coverage.status == "partial"
    assert compiled.league.scoring.misc.return_yd == 0.0
    assert compiled.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="return_yd", value=0.1, reason="unmapped")
    ]


def test_te_premium_from_rec_te_absolute_including_zero_and_negative() -> None:
    positive = compile_league(_base_league(scoring_settings={"rec": 1.0, "rec_te": 1.5}))
    assert positive.te_premium is True
    assert positive.league.scoring.receiving.te_premium == 0.5
    assert positive.coverage.status == "full"
    assert positive.coverage.supported_keys == ["rec", "rec_te"]

    zero = compile_league(_base_league(scoring_settings={"rec": 1.0, "rec_te": 1.0}))
    assert zero.te_premium is False
    assert zero.league.scoring.receiving.te_premium == 0.0
    assert "rec_te" in zero.coverage.supported_keys
    assert zero.coverage.status == "full"

    negative = compile_league(_base_league(scoring_settings={"rec": 1.0, "rec_te": 0.5}))
    assert negative.te_premium is True
    assert negative.league.scoring.receiving.te_premium == -0.5
    assert "rec_te" in negative.coverage.supported_keys


def test_te_premium_score_week_oracle_vs_wr() -> None:
    positive = compile_league(_base_league(scoring_settings={"rec": 1.0, "rec_te": 1.5}))
    rules = positive.league.scoring
    stats = PlayerWeekStats(rec=6)
    assert score_week(stats, rules, position="TE") == 9.0
    assert score_week(stats, rules, position="WR") == 6.0

    negative = compile_league(_base_league(scoring_settings={"rec": 1.0, "rec_te": 0.5}))
    rules = negative.league.scoring
    assert score_week(stats, rules, position="TE") == 3.0
    assert score_week(stats, rules, position="WR") == 6.0


def test_te_premium_conflict_applies_bonus_rec_te() -> None:
    compiled = compile_league(
        _base_league(scoring_settings={"rec": 1.0, "rec_te": 2.0, "bonus_rec_te": 0.5})
    )

    assert compiled.te_premium is True
    assert compiled.league.scoring.receiving.te_premium == 0.5
    assert compiled.coverage.status == "partial"
    assert "bonus_rec_te" in compiled.coverage.supported_keys
    assert "rec_te" not in compiled.coverage.supported_keys
    assert compiled.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="rec_te", value=2.0, reason="conflict")
    ]


def test_te_premium_bonus_and_rec_te_consistent() -> None:
    compiled = compile_league(
        _base_league(scoring_settings={"rec": 1.0, "rec_te": 1.5, "bonus_rec_te": 0.5})
    )

    assert compiled.league.scoring.receiving.te_premium == 0.5
    assert compiled.coverage.status == "full"
    assert compiled.coverage.supported_keys == ["bonus_rec_te", "rec", "rec_te"]


def test_two_qb_marks_superflex() -> None:
    compiled = compile_league(
        _base_league(roster_positions=["QB", "QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"])
    )

    assert compiled.superflex is True
    assert compiled.league.roster.qb == 2
    assert compiled.league.roster.superflex == 0


def test_wrrb_flex_and_rec_flex_count_as_flex() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=[
                "QB",
                "RB",
                "WR",
                "TE",
                "FLEX",
                "WRRB_FLEX",
                "REC_FLEX",
                "BN",
            ]
        )
    )

    assert compiled.league.roster.flex == 3


def test_best_ball_and_keeper_dynasty_mappings() -> None:
    best_ball = compile_league(_base_league(settings={"type": 2, "best_ball": 1}))
    assert best_ball.best_ball is True
    assert best_ball.league.format == "best_ball"

    keeper = compile_league(_base_league(settings={"type": 1, "best_ball": 0}))
    assert keeper.best_ball is False
    assert keeper.league.format == "keeper"

    dynasty = compile_league(_base_league(settings={"type": 2, "best_ball": 0}))
    assert dynasty.league.format == "dynasty"

    redraft = compile_league(_base_league(settings={"type": 0}))
    assert redraft.league.format == "redraft"


def test_unknown_settings_type_defaults_redraft() -> None:
    missing = compile_league({"league_id": "x", "name": "Empty", "season": "2025"})
    assert missing.league.format == "redraft"

    malformed = compile_league(_base_league(settings={"type": "dynasty"}))
    assert malformed.league.format == "redraft"

    out_of_range = compile_league(_base_league(settings={"type": 9}))
    assert out_of_range.league.format == "redraft"


def test_exclusive_yardage_bonuses_score_exactly_through_score_week() -> None:
    pass_compiled = compile_league(
        _base_league(
            scoring_settings={
                "pass_yd": 0.04,
                "bonus_pass_yd_300": 3.0,
                "bonus_pass_yd_400": 5.0,
            }
        )
    )
    assert pass_compiled.league.scoring.passing.pass_yardage_bonuses == [
        YardageBonus(threshold=300.0, points=3.0),
        YardageBonus(threshold=400.0, points=2.0),
    ]
    pass_rules = pass_compiled.league.scoring
    assert score_week(PlayerWeekStats(pass_yd=299), pass_rules) == 11.96
    assert score_week(PlayerWeekStats(pass_yd=300), pass_rules) == 15.0
    assert score_week(PlayerWeekStats(pass_yd=400), pass_rules) == 21.0

    rush_compiled = compile_league(
        _base_league(
            scoring_settings={
                "rush_yd": 0.1,
                "bonus_rush_yd_100": 2.0,
                "bonus_rush_yd_200": 5.0,
            }
        )
    )
    rush_rules = rush_compiled.league.scoring
    assert score_week(PlayerWeekStats(rush_yd=100), rush_rules) == 12.0
    assert score_week(PlayerWeekStats(rush_yd=200), rush_rules) == 25.0

    rec_compiled = compile_league(
        _base_league(
            scoring_settings={
                "rec": 0.0,
                "rec_yd": 0.1,
                "bonus_rec_yd_100": 2.0,
                "bonus_rec_yd_200": 4.0,
            }
        )
    )
    rec_rules = rec_compiled.league.scoring
    assert score_week(PlayerWeekStats(rec_yd=100), rec_rules) == 12.0
    assert score_week(PlayerWeekStats(rec_yd=200), rec_rules) == 24.0


def test_sparse_ranges_preserve_defaults_and_override_supplied() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=["QB", "RB", "WR", "TE", "DEF", "BN"],
            scoring_settings={
                "pts_allow_0": 12.0,
                "pts_allow_35p": -6.0,
                "fgm_40_49": 4.5,
                "yds_allow_200_299": -1.0,
            },
        )
    )

    assert compiled.league.scoring.defense.points_allowed_ranges == [
        RangeRule(min_value=0.0, max_value=0.0, points=12.0),
        RangeRule(min_value=1.0, max_value=6.0, points=7.0),
        RangeRule(min_value=7.0, max_value=13.0, points=4.0),
        RangeRule(min_value=14.0, max_value=20.0, points=1.0),
        RangeRule(min_value=21.0, max_value=27.0, points=0.0),
        RangeRule(min_value=28.0, max_value=34.0, points=-1.0),
        RangeRule(min_value=35.0, max_value=None, points=-6.0),
    ]
    assert compiled.league.scoring.kicking.fg_made_ranges == [
        RangeRule(min_value=0.0, max_value=19.0, points=3.0),
        RangeRule(min_value=20.0, max_value=29.0, points=3.0),
        RangeRule(min_value=30.0, max_value=39.0, points=3.0),
        RangeRule(min_value=40.0, max_value=49.0, points=4.5),
        RangeRule(min_value=50.0, max_value=None, points=5.0),
    ]
    assert compiled.league.scoring.defense.yards_allowed_ranges == [
        RangeRule(min_value=200.0, max_value=299.0, points=-1.0),
    ]


def test_yards_allowed_ranges_score_week_dst() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=["QB", "DEF", "BN"],
            scoring_settings={
                "sack": 0.0,
                "int": 0.0,
                "fum_rec": 0.0,
                "def_td": 0.0,
                "safe": 0.0,
                "blk_kick": 0.0,
                "yds_allow_0_100": 5.0,
                "yds_allow_100_199": 2.0,
                "yds_allow_200_299": 0.0,
                "yds_allow_300_349": -1.0,
                "yds_allow_350_399": -2.0,
                "yds_allow_400_449": -3.0,
                "yds_allow_450_499": -4.0,
                "yds_allow_500_549": -5.0,
                "yds_allow_550p": -6.0,
            },
        )
    )
    assert compiled.coverage.status == "full"
    assert compiled.league.scoring.defense.yards_allowed_ranges[:2] == [
        RangeRule(min_value=0.0, max_value=99.0, points=5.0),
        RangeRule(min_value=100.0, max_value=199.0, points=2.0),
    ]
    rules = compiled.league.scoring
    assert score_week(PlayerWeekStats(dst_yards_allowed=50), rules, position="DST") == 5.0
    # Sleeper boundary: 99 is "less than 100"; exactly 100 belongs to 100-199.
    assert score_week(PlayerWeekStats(dst_yards_allowed=99), rules, position="DST") == 5.0
    assert score_week(PlayerWeekStats(dst_yards_allowed=100), rules, position="DST") == 2.0
    assert score_week(PlayerWeekStats(dst_yards_allowed=150), rules, position="DST") == 2.0
    assert score_week(PlayerWeekStats(dst_yards_allowed=199), rules, position="DST") == 2.0
    assert score_week(PlayerWeekStats(dst_yards_allowed=200), rules, position="DST") == 0.0
    assert score_week(PlayerWeekStats(dst_yards_allowed=320), rules, position="DST") == -1.0
    assert score_week(PlayerWeekStats(dst_yards_allowed=600), rules, position="DST") == -6.0


def test_missing_sections_use_safe_defaults() -> None:
    compiled = compile_league({"league_id": "x", "name": "Empty", "season": "2025"})

    assert isinstance(compiled, CompiledRules)
    assert compiled.coverage == CoverageReport(
        status="full",
        supported_keys=[],
        unsupported_keys=[],
        ignored_zero_keys=[],
    )
    assert compiled.league.format == "redraft"
    assert compiled.league.scoring.receiving.rec == 1.0
    assert compiled.league.scoring.passing.pass_td == 4.0
    assert compiled.league.roster.qb == 1
    assert compiled.matchup.style == "h2h"
    assert compiled.superflex is False
    assert compiled.te_premium is False
    assert compiled.best_ball is False


def test_empty_roster_is_zero_slots_missing_roster_keeps_defaults() -> None:
    empty = compile_league(_base_league(roster_positions=[]))
    assert empty.league.roster.qb == 0
    assert empty.league.roster.flex == 0
    assert empty.league.roster.dst == 0

    missing = compile_league({"league_id": "x", "name": "n", "season": "2025"})
    assert missing.league.roster.qb == 1
    assert missing.league.roster.dst == 1


def test_fum_rec_offensive_when_def_absent_and_dst_when_present() -> None:
    no_def = compile_league(_base_league(scoring_settings={"fum_rec": 1.0, "fum_rec_td": 6.0}))
    assert no_def.league.roster.dst == 0
    assert no_def.league.scoring.misc.fumble_rec == 1.0
    assert no_def.league.scoring.misc.fumble_rec_td == 6.0
    assert no_def.league.scoring.defense.fumble_recovery == 2.0
    assert no_def.coverage.status == "full"

    with_def = compile_league(
        _base_league(
            roster_positions=["QB", "DEF", "BN"],
            scoring_settings={"fum_rec": 3.0, "def_td": 6.0},
        )
    )
    assert with_def.league.scoring.defense.fumble_recovery == 3.0
    assert with_def.league.scoring.misc.fumble_rec == 0.0


def test_fum_rec_td_conflicts_with_def_td() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=["QB", "DEF", "BN"],
            scoring_settings={"def_td": 6.0, "fum_rec_td": 4.0},
        )
    )

    assert compiled.league.scoring.defense.td == 6.0
    assert compiled.coverage.status == "partial"
    assert compiled.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="fum_rec_td", value=4.0, reason="conflict")
    ]


def test_idp_path_compiles() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=["QB", "LB", "DB", "IDP_FLEX", "BN"],
            scoring_settings={
                "idp_tkl_solo": 1.5,
                "idp_tkl_ast": 0.75,
                "idp_sack": 3.0,
                "idp_int": 4.0,
            },
        )
    )

    assert compiled.league.roster.idp == 3
    assert compiled.league.scoring.idp.solo_tackle == 1.5
    assert compiled.league.scoring.idp.assisted_tackle == 0.75
    assert compiled.league.scoring.idp.sack == 3.0
    assert compiled.league.scoring.idp.interception == 4.0
    assert (
        score_week(
            PlayerWeekStats(idp_solo_tackle=2, idp_sack=1),
            compiled.league.scoring,
            position="LB",
        )
        == 6.0
    )


def test_dst_without_def_is_unsupported_or_ignored() -> None:
    nonzero = compile_league(
        _base_league(scoring_settings={"sack": 1.0, "pts_allow_0": 10.0, "int": 2.0})
    )
    assert nonzero.coverage.status == "partial"
    assert {item.key for item in nonzero.coverage.unsupported_keys} == {
        "sack",
        "pts_allow_0",
        "int",
    }
    assert nonzero.league.scoring.defense.sack == 1.0  # default preserved

    zero = compile_league(_base_league(scoring_settings={"sack": 0.0, "int": 0.0}))
    assert zero.coverage.status == "full"
    assert zero.coverage.ignored_zero_keys == ["int", "sack"]


def test_non_numeric_and_bool_scoring_values_are_partial() -> None:
    string_td = compile_league(_base_league(scoring_settings={"pass_td": "6"}))
    assert string_td.coverage.status == "partial"
    assert string_td.league.scoring.passing.pass_td == 4.0
    assert string_td.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="pass_td", value="6", reason="unmapped")
    ]

    bool_td = compile_league(_base_league(scoring_settings={"pass_td": True}))
    assert bool_td.coverage.status == "partial"
    assert bool_td.league.scoring.passing.pass_td == 4.0
    assert bool_td.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="pass_td", value=True, reason="unmapped")
    ]

    nested = compile_league(_base_league(scoring_settings={"pass_td": {"pts": 6}}))
    assert nested.coverage.status == "partial"
    assert nested.coverage.unsupported_keys[0].key == "pass_td"
    assert isinstance(nested.coverage.unsupported_keys[0].value, str)


def test_unrepresentable_split_50_plus_preserves_default_range() -> None:
    compiled = compile_league(_base_league(scoring_settings={"fgm_50_59": 5.0, "fgm_60p": 6.0}))

    assert compiled.coverage.status == "partial"
    assert compiled.league.scoring.kicking.fg_made_ranges[-1] == RangeRule(
        min_value=50.0, max_value=None, points=5.0
    )
    assert {item.key for item in compiled.coverage.unsupported_keys} == {
        "fgm_50_59",
        "fgm_60p",
    }
    assert all(
        item.reason == "exclusive_range_unrepresentable"
        for item in compiled.coverage.unsupported_keys
    )
    # Default 50+ scoring remains 5 points.
    assert (
        score_week(
            PlayerWeekStats(fg_made_50_plus=1),
            compiled.league.scoring,
            position="K",
        )
        == 5.0
    )


def test_absent_keys_never_erase_defaults() -> None:
    compiled = compile_league(_base_league(scoring_settings={"pass_td": 6.0}))

    assert compiled.league.scoring.passing.pass_td == 6.0
    assert compiled.league.scoring.passing.pass_yd == 0.04
    assert compiled.league.scoring.receiving.rec == 1.0
    assert compiled.league.scoring.misc.fumble_lost == -2.0


def test_compiler_module_has_no_io_imports() -> None:
    tree = ast.parse(_COMPILER_PATH.read_text())
    forbidden = {
        "os",
        "sys",
        "pathlib",
        "urllib",
        "http",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "sqlite3",
        "asyncio",
        "aiohttp",
    }
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported.isdisjoint(forbidden)
    assert "razzle_api" in imported or "typing" in imported
