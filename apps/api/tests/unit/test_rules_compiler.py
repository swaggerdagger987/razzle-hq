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


def test_te_premium_from_rec_te_delta() -> None:
    compiled = compile_league(
        _base_league(scoring_settings={"rec": 1.0, "rec_te": 1.5})
    )

    assert compiled.te_premium is True
    assert compiled.league.scoring.receiving.te_premium == 0.5
    assert compiled.coverage.status == "full"
    assert compiled.coverage.supported_keys == ["rec", "rec_te"]


def test_te_premium_conflict_applies_bonus_rec_te() -> None:
    compiled = compile_league(
        _base_league(
            scoring_settings={"rec": 1.0, "rec_te": 2.0, "bonus_rec_te": 0.5}
        )
    )

    assert compiled.te_premium is True
    assert compiled.league.scoring.receiving.te_premium == 0.5
    assert compiled.coverage.status == "partial"
    assert "bonus_rec_te" in compiled.coverage.supported_keys
    assert compiled.coverage.unsupported_keys == [
        UnsupportedScoringKey(key="rec_te", value=2.0, reason="conflict")
    ]


def test_two_qb_marks_superflex() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=["QB", "QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"]
        )
    )

    assert compiled.superflex is True
    assert compiled.league.roster.qb == 2
    assert compiled.league.roster.superflex == 0


def test_best_ball_and_keeper_dynasty_mappings() -> None:
    best_ball = compile_league(
        _base_league(settings={"type": 2, "best_ball": 1})
    )
    assert best_ball.best_ball is True
    assert best_ball.league.format == "best_ball"

    keeper = compile_league(_base_league(settings={"type": 1, "best_ball": 0}))
    assert keeper.best_ball is False
    assert keeper.league.format == "keeper"

    dynasty = compile_league(_base_league(settings={"type": 2, "best_ball": 0}))
    assert dynasty.league.format == "dynasty"

    redraft = compile_league(_base_league(settings={"type": 0}))
    assert redraft.league.format == "redraft"


def test_exclusive_yardage_bonuses_score_exactly_through_score_week() -> None:
    compiled = compile_league(
        _base_league(
            scoring_settings={
                "pass_yd": 0.04,
                "bonus_pass_yd_300": 3.0,
                "bonus_pass_yd_400": 5.0,
            }
        )
    )
    bonuses = compiled.league.scoring.passing.pass_yardage_bonuses
    assert bonuses == [
        YardageBonus(threshold=300.0, points=3.0),
        YardageBonus(threshold=400.0, points=2.0),
    ]

    rules = compiled.league.scoring
    low = score_week(PlayerWeekStats(pass_yd=300), rules)
    high = score_week(PlayerWeekStats(pass_yd=400), rules)
    below = score_week(PlayerWeekStats(pass_yd=299), rules)

    assert below == 11.96
    assert low == 15.0
    assert high == 21.0


def test_range_replacement_missing_bucket_is_zero() -> None:
    compiled = compile_league(
        _base_league(
            roster_positions=["QB", "RB", "WR", "TE", "DEF", "BN"],
            scoring_settings={
                "pts_allow_0": 12.0,
                "pts_allow_35p": -6.0,
                "fgm_40_49": 4.5,
            },
        )
    )

    assert compiled.league.scoring.defense.points_allowed_ranges == [
        RangeRule(min_value=0.0, max_value=0.0, points=12.0),
        RangeRule(min_value=1.0, max_value=6.0, points=0.0),
        RangeRule(min_value=7.0, max_value=13.0, points=0.0),
        RangeRule(min_value=14.0, max_value=20.0, points=0.0),
        RangeRule(min_value=21.0, max_value=27.0, points=0.0),
        RangeRule(min_value=28.0, max_value=34.0, points=0.0),
        RangeRule(min_value=35.0, max_value=None, points=-6.0),
    ]
    assert compiled.league.scoring.kicking.fg_made_ranges == [
        RangeRule(min_value=0.0, max_value=19.0, points=0.0),
        RangeRule(min_value=20.0, max_value=29.0, points=0.0),
        RangeRule(min_value=30.0, max_value=39.0, points=0.0),
        RangeRule(min_value=40.0, max_value=49.0, points=4.5),
        RangeRule(min_value=50.0, max_value=None, points=0.0),
    ]


def test_missing_sections_use_safe_defaults() -> None:
    compiled = compile_league({"league_id": "x", "name": "Empty", "season": "2025"})

    assert isinstance(compiled, CompiledRules)
    assert compiled.coverage == CoverageReport(
        status="full",
        supported_keys=[],
        unsupported_keys=[],
        ignored_zero_keys=[],
    )
    assert compiled.league.format == "dynasty"
    assert compiled.league.scoring.receiving.rec == 1.0
    assert compiled.league.scoring.passing.pass_td == 4.0
    assert compiled.league.roster.qb == 1
    assert compiled.matchup.style == "h2h"
    assert compiled.superflex is False
    assert compiled.te_premium is False
    assert compiled.best_ball is False


def test_fum_rec_is_offensive_misc_when_def_absent() -> None:
    compiled = compile_league(
        _base_league(scoring_settings={"fum_rec": 1.0, "fum_rec_td": 6.0})
    )

    assert compiled.league.roster.dst == 0
    assert compiled.league.scoring.misc.fumble_rec == 1.0
    assert compiled.league.scoring.misc.fumble_rec_td == 6.0
    assert compiled.league.scoring.defense.fumble_recovery == 2.0
    assert compiled.coverage.status == "full"


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
