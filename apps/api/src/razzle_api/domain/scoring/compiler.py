"""Pure Sleeper league → CompiledRules compiler.

No I/O: maps scoring_settings and league settings onto existing LeagueConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from razzle_api.domain.scoring.config import (
    DefenseRules,
    IdpRules,
    KickingRules,
    LeagueConfig,
    LeagueFormat,
    MiscRules,
    PassingRules,
    RangeRule,
    ReceivingRules,
    RosterConfig,
    RushingRules,
    ScoringRules,
    WaiverType,
    YardageBonus,
)

_EPS = 1e-12

UnsupportedReason = Literal["unmapped", "exclusive_range_unrepresentable", "conflict"]
CoverageStatus = Literal["full", "partial"]
MatchupStyle = Literal["h2h", "h2h_median"]
TiebreakerKey = Literal["record", "points_for", "points_against"]
UnsupportedValue = bool | int | float | str | None

_TIEBREAKER_ORDER: list[TiebreakerKey] = ["record", "points_for", "points_against"]

_FORMAT_BY_TYPE: dict[int, LeagueFormat] = {
    0: "redraft",
    1: "keeper",
    2: "dynasty",
}

_WAIVER_BY_TYPE: dict[int, WaiverType] = {
    0: "rolling",
    1: "reverse",
    2: "faab",
}

_PASSING_DIRECT: dict[str, str] = {
    "pass_att": "pass_att",
    "pass_cmp": "pass_cmp",
    "pass_inc": "pass_inc",
    "pass_yd": "pass_yd",
    "pass_td": "pass_td",
    "pass_int": "pass_int",
    "pass_sack": "pass_sack",
    "pass_2pt": "pass_two_pt",
    "pass_fd": "pass_first_down",
    "pass_cmp_40": "pass_40_yd_bonus",
    "pass_td_40": "pass_40_yd_td_bonus",
}

_RUSHING_DIRECT: dict[str, str] = {
    "rush_att": "rush_att",
    "rush_yd": "rush_yd",
    "rush_td": "rush_td",
    "rush_2pt": "rush_two_pt",
    "rush_fd": "rush_first_down",
    "rush_40": "rush_40_yd_bonus",
    "rush_td_40": "rush_40_yd_td_bonus",
}

_RECEIVING_DIRECT: dict[str, str] = {
    "target": "target",
    "rec": "rec",
    "rec_yd": "rec_yd",
    "rec_td": "rec_td",
    "rec_2pt": "rec_two_pt",
    "rec_fd": "rec_first_down",
    "rec_40": "rec_40_yd_bonus",
    "rec_td_40": "rec_40_yd_td_bonus",
}

_MISC_DIRECT: dict[str, str] = {
    "fum": "fumble",
    "fum_lost": "fumble_lost",
    "st_td": "special_teams_td",
    "2pt": "two_pt",
}

_KICKING_DIRECT: dict[str, str] = {
    "xpm": "pat_made",
    "xpmiss": "pat_missed",
    "fgm": "fg_made",
    "fgmiss": "fg_missed",
}

_DEFENSE_SCALARS: dict[str, str] = {
    "sack": "sack",
    "int": "interception",
    "def_td": "td",
    "safe": "safety",
    "blk_kick": "blocked_kick",
    "ff": "forced_fumble",
    "tkl_loss": "tackle_for_loss",
    "qb_hit": "qb_hit",
}

_IDP_DIRECT: dict[str, str] = {
    "idp_tkl_solo": "solo_tackle",
    "idp_tkl_ast": "assisted_tackle",
    "idp_tkl_loss": "tackle_for_loss",
    "idp_sack": "sack",
    "idp_qb_hit": "qb_hit",
    "idp_int": "interception",
    "idp_pass_def": "pass_defended",
    "idp_ff": "forced_fumble",
    "idp_fum_rec": "fumble_recovery",
    "idp_td": "td",
    "idp_safe": "safety",
    "idp_blk_kick": "blocked_kick",
}

_YARDAGE_BONUS_KEYS: dict[str, tuple[str, float]] = {
    "bonus_pass_yd_300": ("passing", 300.0),
    "bonus_pass_yd_400": ("passing", 400.0),
    "bonus_rush_yd_100": ("rushing", 100.0),
    "bonus_rush_yd_200": ("rushing", 200.0),
    "bonus_rec_yd_100": ("receiving", 100.0),
    "bonus_rec_yd_200": ("receiving", 200.0),
}

_YARDAGE_PAIRS: list[tuple[str, str, str]] = [
    ("passing", "bonus_pass_yd_300", "bonus_pass_yd_400"),
    ("rushing", "bonus_rush_yd_100", "bonus_rush_yd_200"),
    ("receiving", "bonus_rec_yd_100", "bonus_rec_yd_200"),
]

_FG_MADE_BUCKETS: list[tuple[str, float, float | None]] = [
    ("fgm_0_19", 0.0, 19.0),
    ("fgm_20_29", 20.0, 29.0),
    ("fgm_30_39", 30.0, 39.0),
    ("fgm_40_49", 40.0, 49.0),
]

_FG_MISS_BUCKETS: list[tuple[str, float, float | None]] = [
    ("fgmiss_0_19", 0.0, 19.0),
    ("fgmiss_20_29", 20.0, 29.0),
    ("fgmiss_30_39", 30.0, 39.0),
    ("fgmiss_40_49", 40.0, 49.0),
]

_FG_MADE_50_KEYS = ("fgm_50_59", "fgm_60p", "fgm_50p")
_FG_MISS_50_KEYS = ("fgmiss_50_59", "fgmiss_60p", "fgmiss_50p")

_PTS_ALLOW_BUCKETS: list[tuple[str, float, float | None]] = [
    ("pts_allow_0", 0.0, 0.0),
    ("pts_allow_1_6", 1.0, 6.0),
    ("pts_allow_7_13", 7.0, 13.0),
    ("pts_allow_14_20", 14.0, 20.0),
    ("pts_allow_21_27", 21.0, 27.0),
    ("pts_allow_28_34", 28.0, 34.0),
    ("pts_allow_35p", 35.0, None),
]

_YDS_ALLOW_BUCKETS: list[tuple[str, float, float | None]] = [
    ("yds_allow_0_100", 0.0, 100.0),
    ("yds_allow_100_199", 100.0, 199.0),
    ("yds_allow_200_299", 200.0, 299.0),
    ("yds_allow_300_349", 300.0, 349.0),
    ("yds_allow_350_399", 350.0, 399.0),
    ("yds_allow_400_449", 400.0, 449.0),
    ("yds_allow_450_499", 450.0, 499.0),
    ("yds_allow_500_549", 500.0, 549.0),
    ("yds_allow_550p", 550.0, None),
]

_ROSTER_SLOT_MAP: dict[str, str] = {
    "QB": "qb",
    "RB": "rb",
    "WR": "wr",
    "TE": "te",
    "FLEX": "flex",
    "WRRB_FLEX": "flex",
    "REC_FLEX": "flex",
    "SUPER_FLEX": "superflex",
    "K": "k",
    "DEF": "dst",
    "BN": "bench",
    "IR": "ir",
    "TAXI": "taxi",
}

_IDP_SLOTS = frozenset({"DL", "LB", "DB", "IDP_FLEX", "IDP"})


class UnsupportedScoringKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: UnsupportedValue
    reason: UnsupportedReason


class CoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CoverageStatus
    supported_keys: list[str] = Field(default_factory=list)
    unsupported_keys: list[UnsupportedScoringKey] = Field(default_factory=list)
    ignored_zero_keys: list[str] = Field(default_factory=list)


class MatchupFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: MatchupStyle
    median_enabled: bool


class TiebreakerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: list[TiebreakerKey] = Field(default_factory=lambda: list(_TIEBREAKER_ORDER))
    playoff_seed_type: int | None = None


class CompiledRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    league_id: str
    name: str
    season: str
    league: LeagueConfig
    matchup: MatchupFormat
    tiebreakers: TiebreakerConfig
    te_premium: bool
    superflex: bool
    best_ball: bool
    coverage: CoverageReport


@dataclass
class _Coverage:
    supported: set[str] = field(default_factory=set)
    unsupported: dict[str, UnsupportedScoringKey] = field(default_factory=dict)
    ignored_zero: set[str] = field(default_factory=set)
    consumed: set[str] = field(default_factory=set)

    def support(self, key: str) -> None:
        self.supported.add(key)
        self.consumed.add(key)

    def reject(
        self,
        key: str,
        value: Any,
        reason: UnsupportedReason = "unmapped",
    ) -> None:
        self.unsupported[key] = UnsupportedScoringKey(
            key=key,
            value=_coverage_value(value),
            reason=reason,
        )
        self.consumed.add(key)

    def report(self) -> CoverageReport:
        return CoverageReport(
            status="partial" if self.unsupported else "full",
            supported_keys=sorted(self.supported),
            unsupported_keys=sorted(self.unsupported.values(), key=lambda item: item.key),
            ignored_zero_keys=sorted(self.ignored_zero),
        )


def compile_league(sleeper_json: dict[str, Any]) -> CompiledRules:
    """Map a Sleeper league payload onto CompiledRules. Pure and deterministic."""
    settings = _as_dict(sleeper_json.get("settings"))
    scoring_raw = _as_dict(sleeper_json.get("scoring_settings"))
    roster_positions = sleeper_json.get("roster_positions")
    if not isinstance(roster_positions, list):
        roster_positions = None

    roster = _compile_roster(roster_positions)
    scoring, coverage = _compile_scoring(scoring_raw, def_rostered=roster.dst > 0)
    league_format, best_ball = _compile_format(settings)
    league = _compile_league_config(
        sleeper_json, settings, roster, scoring, league_format=league_format
    )
    matchup, tiebreakers = _compile_match_meta(settings)

    return CompiledRules(
        league_id=str(sleeper_json.get("league_id") or ""),
        name=str(sleeper_json.get("name") or ""),
        season=str(sleeper_json.get("season") or ""),
        league=league,
        matchup=matchup,
        tiebreakers=tiebreakers,
        te_premium=abs(scoring.receiving.te_premium) > _EPS,
        superflex=roster.superflex > 0 or roster.qb >= 2,
        best_ball=best_ball,
        coverage=coverage,
    )


def _compile_scoring(
    scoring_raw: dict[str, Any],
    *,
    def_rostered: bool,
) -> tuple[ScoringRules, CoverageReport]:
    cov = _Coverage()
    passing = PassingRules()
    rushing = RushingRules()
    receiving = ReceivingRules()
    misc = MiscRules()
    kicking = KickingRules()
    defense = DefenseRules()
    idp = IdpRules()

    _apply_direct(scoring_raw, _PASSING_DIRECT, passing, cov)
    _apply_direct(scoring_raw, _RUSHING_DIRECT, rushing, cov)
    _apply_direct(scoring_raw, _RECEIVING_DIRECT, receiving, cov)
    _apply_direct(scoring_raw, _MISC_DIRECT, misc, cov)
    _apply_direct(scoring_raw, _KICKING_DIRECT, kicking, cov)
    _apply_direct(scoring_raw, _IDP_DIRECT, idp, cov)
    _apply_te_premium(scoring_raw, receiving, cov)
    _apply_yardage_bonuses(
        scoring_raw,
        {
            "passing": (passing, "pass_yardage_bonuses"),
            "rushing": (rushing, "rush_yardage_bonuses"),
            "receiving": (receiving, "rec_yardage_bonuses"),
        },
        cov,
    )
    _apply_fg_family(scoring_raw, kicking, made=True, cov=cov)
    _apply_fg_family(scoring_raw, kicking, made=False, cov=cov)
    _apply_defense(scoring_raw, defense, misc, def_rostered=def_rostered, cov=cov)
    _finalize_unknown(scoring_raw, cov)

    scoring = ScoringRules(
        passing=passing,
        rushing=rushing,
        receiving=receiving,
        misc=misc,
        kicking=kicking,
        defense=defense,
        idp=idp,
    )
    return scoring, cov.report()


def _compile_league_config(
    sleeper_json: dict[str, Any],
    settings: dict[str, Any],
    roster: RosterConfig,
    scoring: ScoringRules,
    *,
    league_format: LeagueFormat,
) -> LeagueConfig:
    league_size = _as_int(sleeper_json.get("total_rosters"))
    if league_size is None:
        league_size = LeagueConfig().league_size

    waiver_type_code = _as_int(settings.get("waiver_type"))
    waiver_type = (
        _WAIVER_BY_TYPE[waiver_type_code]
        if waiver_type_code in _WAIVER_BY_TYPE
        else LeagueConfig().waiver_type
    )

    return LeagueConfig(
        league_size=league_size,
        format=league_format,
        scoring=scoring,
        roster=roster,
        waiver_type=waiver_type,
        faab_budget=_int_or_default(settings.get("waiver_budget"), LeagueConfig().faab_budget),
        trade_deadline_week=_int_or_default(
            settings.get("trade_deadline"), LeagueConfig().trade_deadline_week
        ),
        playoff_teams=_int_or_default(settings.get("playoff_teams"), LeagueConfig().playoff_teams),
        playoff_start_week=_int_or_default(
            settings.get("playoff_week_start"), LeagueConfig().playoff_start_week
        ),
    )


def _compile_match_meta(settings: dict[str, Any]) -> tuple[MatchupFormat, TiebreakerConfig]:
    median_enabled = _as_int(settings.get("league_average_match")) == 1
    matchup = MatchupFormat(
        style="h2h_median" if median_enabled else "h2h",
        median_enabled=median_enabled,
    )
    tiebreakers = TiebreakerConfig(
        order=list(_TIEBREAKER_ORDER),
        playoff_seed_type=_as_int(settings.get("playoff_seed_type")),
    )
    return matchup, tiebreakers


def _apply_direct(
    scoring_raw: dict[str, Any],
    mapping: dict[str, str],
    target: BaseModel,
    cov: _Coverage,
) -> None:
    for sleeper_key, field_name in mapping.items():
        if sleeper_key not in scoring_raw:
            continue
        number = _take_number(scoring_raw, sleeper_key, cov)
        if number is None:
            continue
        setattr(target, field_name, number)
        cov.support(sleeper_key)


def _apply_te_premium(
    scoring_raw: dict[str, Any],
    receiving: ReceivingRules,
    cov: _Coverage,
) -> None:
    has_bonus = "bonus_rec_te" in scoring_raw
    has_rec_te = "rec_te" in scoring_raw
    bonus_val = _take_number(scoring_raw, "bonus_rec_te", cov) if has_bonus else None
    rec_te_val = _take_number(scoring_raw, "rec_te", cov) if has_rec_te else None

    if has_bonus and bonus_val is not None:
        receiving.te_premium = bonus_val
        cov.support("bonus_rec_te")

    if not (has_rec_te and rec_te_val is not None):
        return

    # rec_te is absolute TE reception value; always derive premium when alone.
    if has_bonus and bonus_val is not None:
        # Consistency: rec + bonus_rec_te == rec_te.
        if abs(receiving.rec + bonus_val - rec_te_val) > _EPS:
            cov.reject("rec_te", rec_te_val, reason="conflict")
        else:
            cov.support("rec_te")
        return

    receiving.te_premium = rec_te_val - receiving.rec
    cov.support("rec_te")


def _apply_yardage_bonuses(
    scoring_raw: dict[str, Any],
    sections: dict[str, tuple[BaseModel, str]],
    cov: _Coverage,
) -> None:
    present_by_section: dict[str, dict[float, float]] = {name: {} for name in sections}

    for key, (section, threshold) in _YARDAGE_BONUS_KEYS.items():
        if key not in scoring_raw:
            continue
        number = _take_number(scoring_raw, key, cov)
        if number is None:
            continue
        present_by_section[section][threshold] = number
        cov.support(key)

    for section, low_key, high_key in _YARDAGE_PAIRS:
        present = present_by_section[section]
        if not present:
            continue
        model, field_name = sections[section]
        by_threshold = {bonus.threshold: bonus.points for bonus in getattr(model, field_name)}
        low_threshold = _YARDAGE_BONUS_KEYS[low_key][1]
        high_threshold = _YARDAGE_BONUS_KEYS[high_key][1]
        if low_threshold in present and high_threshold in present:
            by_threshold[low_threshold] = present[low_threshold]
            by_threshold[high_threshold] = present[high_threshold] - present[low_threshold]
        else:
            by_threshold.update(present)
        setattr(
            model,
            field_name,
            [
                YardageBonus(threshold=threshold, points=points)
                for threshold, points in sorted(by_threshold.items())
            ],
        )


def _apply_fg_family(
    scoring_raw: dict[str, Any],
    kicking: KickingRules,
    *,
    made: bool,
    cov: _Coverage,
) -> None:
    buckets = _FG_MADE_BUCKETS if made else _FG_MISS_BUCKETS
    plus_keys = _FG_MADE_50_KEYS if made else _FG_MISS_50_KEYS
    field_name = "fg_made_ranges" if made else "fg_missed_ranges"
    current: list[RangeRule] = list(getattr(kicking, field_name))
    updated = _overlay_range_buckets(scoring_raw, buckets, current, cov)
    updated = _overlay_fg_50_plus(scoring_raw, plus_keys, updated, cov)
    setattr(kicking, field_name, updated)


def _overlay_range_buckets(
    scoring_raw: dict[str, Any],
    buckets: list[tuple[str, float, float | None]],
    current: list[RangeRule],
    cov: _Coverage,
) -> list[RangeRule]:
    """Override only supplied buckets; preserve absent defaults."""
    if not any(key in scoring_raw for key, _min, _max in buckets):
        return current

    by_bounds = {(rule.min_value, rule.max_value): rule.points for rule in current}
    changed = False
    for key, min_value, max_value in buckets:
        if key not in scoring_raw:
            continue
        number = _take_number(scoring_raw, key, cov)
        if number is None:
            continue
        by_bounds[(min_value, max_value)] = number
        cov.support(key)
        changed = True
    if not changed:
        return current
    return _ranges_from_bounds(by_bounds)


def _overlay_fg_50_plus(
    scoring_raw: dict[str, Any],
    plus_keys: tuple[str, ...],
    current: list[RangeRule],
    cov: _Coverage,
) -> list[RangeRule]:
    present: list[tuple[str, float]] = []
    for key in plus_keys:
        if key not in scoring_raw:
            continue
        number = _take_number(scoring_raw, key, cov)
        if number is None:
            continue
        present.append((key, number))
    if not present:
        return current

    values = [value for _key, value in present]
    if max(values) - min(values) > _EPS:
        for key, value in present:
            cov.reject(key, value, reason="exclusive_range_unrepresentable")
        # Leave existing 50+ range untouched.
        return current

    by_bounds = {(rule.min_value, rule.max_value): rule.points for rule in current}
    by_bounds[(50.0, None)] = values[0]
    for key, _value in present:
        cov.support(key)
    return _ranges_from_bounds(by_bounds)


def _apply_defense(
    scoring_raw: dict[str, Any],
    defense: DefenseRules,
    misc: MiscRules,
    *,
    def_rostered: bool,
    cov: _Coverage,
) -> None:
    defense.points_allowed_ranges = _apply_gated_ranges(
        scoring_raw,
        _PTS_ALLOW_BUCKETS,
        defense.points_allowed_ranges,
        def_rostered=def_rostered,
        cov=cov,
    )
    defense.yards_allowed_ranges = _apply_gated_ranges(
        scoring_raw,
        _YDS_ALLOW_BUCKETS,
        defense.yards_allowed_ranges,
        def_rostered=def_rostered,
        cov=cov,
    )
    _apply_defense_scalars(scoring_raw, defense, def_rostered=def_rostered, cov=cov)
    _apply_fum_rec(scoring_raw, defense, misc, def_rostered=def_rostered, cov=cov)


def _apply_gated_ranges(
    scoring_raw: dict[str, Any],
    buckets: list[tuple[str, float, float | None]],
    current: list[RangeRule],
    *,
    def_rostered: bool,
    cov: _Coverage,
) -> list[RangeRule]:
    present_keys = [key for key, _min, _max in buckets if key in scoring_raw]
    if not present_keys:
        return current
    if not def_rostered:
        _reject_or_defer_gated_keys(scoring_raw, present_keys, cov)
        return current
    return _overlay_range_buckets(scoring_raw, buckets, list(current), cov)


def _reject_or_defer_gated_keys(
    scoring_raw: dict[str, Any],
    keys: list[str],
    cov: _Coverage,
) -> None:
    """DEF-gated keys without DEF: non-numeric/nonzero unsupported; zero deferred."""
    for key in keys:
        raw = scoring_raw[key]
        if not _is_numeric(raw):
            cov.reject(key, raw)
            continue
        if abs(float(raw)) > _EPS:
            cov.reject(key, float(raw))


def _apply_defense_scalars(
    scoring_raw: dict[str, Any],
    defense: DefenseRules,
    *,
    def_rostered: bool,
    cov: _Coverage,
) -> None:
    for key, field_name in _DEFENSE_SCALARS.items():
        if key not in scoring_raw:
            continue
        if not def_rostered:
            # Non-numeric rejected now; numeric zero/nonzero deferred to finalize.
            if not _is_numeric(scoring_raw[key]):
                cov.reject(key, scoring_raw[key])
            continue
        number = _take_number(scoring_raw, key, cov)
        if number is None:
            continue
        setattr(defense, field_name, number)
        cov.support(key)


def _apply_fum_rec(
    scoring_raw: dict[str, Any],
    defense: DefenseRules,
    misc: MiscRules,
    *,
    def_rostered: bool,
    cov: _Coverage,
) -> None:
    for key, misc_field, def_field in (
        ("fum_rec", "fumble_rec", "fumble_recovery"),
        ("fum_rec_td", "fumble_rec_td", "td"),
    ):
        if key not in scoring_raw:
            continue
        number = _take_number(scoring_raw, key, cov)
        if number is None:
            continue
        if not def_rostered:
            setattr(misc, misc_field, number)
            cov.support(key)
            continue
        if key == "fum_rec_td" and "def_td" in scoring_raw:
            def_td_val = _peek_number(scoring_raw, "def_td")
            if def_td_val is not None and abs(def_td_val - number) > _EPS:
                cov.reject(key, number, reason="conflict")
                continue
        setattr(defense, def_field, number)
        cov.support(key)


def _finalize_unknown(scoring_raw: dict[str, Any], cov: _Coverage) -> None:
    for key, raw_value in scoring_raw.items():
        if key in cov.consumed:
            continue
        if not _is_numeric(raw_value):
            cov.reject(key, raw_value)
            continue
        value = float(raw_value)
        if abs(value) <= _EPS:
            cov.ignored_zero.add(key)
            cov.consumed.add(key)
        else:
            cov.reject(key, value)


def _compile_roster(roster_positions: list[Any] | None) -> RosterConfig:
    if roster_positions is None:
        return RosterConfig()

    counts = {
        "qb": 0,
        "rb": 0,
        "wr": 0,
        "te": 0,
        "flex": 0,
        "superflex": 0,
        "k": 0,
        "dst": 0,
        "idp": 0,
        "bench": 0,
        "ir": 0,
        "taxi": 0,
    }
    for slot in roster_positions:
        if not isinstance(slot, str):
            continue
        if slot in _IDP_SLOTS:
            counts["idp"] += 1
            continue
        field_name = _ROSTER_SLOT_MAP.get(slot)
        if field_name is not None:
            counts[field_name] += 1
    return RosterConfig(**counts)


def _compile_format(settings: dict[str, Any]) -> tuple[LeagueFormat, bool]:
    best_ball = _as_int(settings.get("best_ball")) == 1
    if best_ball:
        return "best_ball", True
    league_type = _as_int(settings.get("type"))
    if league_type in _FORMAT_BY_TYPE:
        return _FORMAT_BY_TYPE[league_type], False
    # Only exact 0/1/2 map; anything else (missing/malformed) defaults redraft.
    return "redraft", False


def _take_number(scoring_raw: dict[str, Any], key: str, cov: _Coverage) -> float | None:
    """Return float for numeric values; reject bool/non-numeric; None if rejected."""
    raw = scoring_raw[key]
    if not _is_numeric(raw):
        cov.reject(key, raw)
        return None
    return float(raw)


def _peek_number(scoring_raw: dict[str, Any], key: str) -> float | None:
    raw = scoring_raw.get(key)
    if not _is_numeric(raw):
        return None
    return float(raw)


def _ranges_from_bounds(by_bounds: dict[tuple[float, float | None], float]) -> list[RangeRule]:
    items = sorted(
        by_bounds.items(),
        key=lambda item: (item[0][0], item[0][1] is not None, item[0][1] or 0.0),
    )
    return [
        RangeRule(min_value=min_value, max_value=max_value, points=points)
        for (min_value, max_value), points in items
    ]


def _coverage_value(value: Any) -> UnsupportedValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    return repr(value)


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _int_or_default(value: Any, default: int) -> int:
    parsed = _as_int(value)
    return default if parsed is None else parsed
