"""Pure Sleeper league → CompiledRules compiler.

No I/O: maps scoring_settings and league settings onto existing LeagueConfig.
"""

from __future__ import annotations

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

# Direct scalar maps: sleeper_key → (section, field)
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

_DEFENSE_DIRECT: dict[str, str] = {
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

_ROSTER_SLOT_MAP: dict[str, str] = {
    "QB": "qb",
    "RB": "rb",
    "WR": "wr",
    "TE": "te",
    "FLEX": "flex",
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
    value: float
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


def compile_league(sleeper_json: dict[str, Any]) -> CompiledRules:
    """Map a Sleeper league payload onto CompiledRules. Pure and deterministic."""
    settings = _as_dict(sleeper_json.get("settings"))
    scoring_raw = _as_dict(sleeper_json.get("scoring_settings"))
    roster_positions = sleeper_json.get("roster_positions")
    if not isinstance(roster_positions, list):
        roster_positions = None

    roster = _compile_roster(roster_positions)
    def_rostered = roster.dst > 0

    passing = PassingRules()
    rushing = RushingRules()
    receiving = ReceivingRules()
    misc = MiscRules()
    kicking = KickingRules()
    defense = DefenseRules()
    idp = IdpRules()

    supported: set[str] = set()
    unsupported: dict[str, UnsupportedScoringKey] = {}
    ignored_zero: set[str] = set()
    consumed: set[str] = set()

    # --- direct section maps ---
    _apply_direct(scoring_raw, _PASSING_DIRECT, passing, supported, consumed)
    _apply_direct(scoring_raw, _RUSHING_DIRECT, rushing, supported, consumed)
    _apply_direct(scoring_raw, _RECEIVING_DIRECT, receiving, supported, consumed)
    _apply_direct(scoring_raw, _MISC_DIRECT, misc, supported, consumed)
    _apply_direct(scoring_raw, _KICKING_DIRECT, kicking, supported, consumed)
    _apply_direct(scoring_raw, _IDP_DIRECT, idp, supported, consumed)

    # TE premium: bonus_rec_te primary; else positive rec_te - rec delta.
    _apply_te_premium(scoring_raw, receiving, supported, unsupported, consumed)

    # Yardage bonuses (exclusive Sleeper tiers → stacking engine bonuses)
    _apply_yardage_bonuses(scoring_raw, passing, rushing, receiving, supported, consumed)

    # Kicking distance families
    _apply_fg_ranges(
        scoring_raw,
        kicking,
        made=True,
        supported=supported,
        unsupported=unsupported,
        consumed=consumed,
    )
    _apply_fg_ranges(
        scoring_raw,
        kicking,
        made=False,
        supported=supported,
        unsupported=unsupported,
        consumed=consumed,
    )

    # DST / offensive fum_rec split
    _apply_defense_and_fum_rec(
        scoring_raw,
        defense,
        misc,
        def_rostered=def_rostered,
        supported=supported,
        unsupported=unsupported,
        consumed=consumed,
    )

    # Remaining keys: known-handled already in consumed; else ignore-zero or unsupported
    for key, raw_value in scoring_raw.items():
        if key in consumed:
            continue
        value = _as_float(raw_value)
        if value is None:
            continue
        if abs(value) <= _EPS:
            ignored_zero.add(key)
        else:
            unsupported[key] = UnsupportedScoringKey(key=key, value=value, reason="unmapped")

    scoring = ScoringRules(
        passing=passing,
        rushing=rushing,
        receiving=receiving,
        misc=misc,
        kicking=kicking,
        defense=defense,
        idp=idp,
    )

    league_format, best_ball = _compile_format(settings)
    league_size = _as_int(sleeper_json.get("total_rosters"))
    if league_size is None:
        league_size = LeagueConfig().league_size

    waiver_type_code = _as_int(settings.get("waiver_type"))
    if waiver_type_code in _WAIVER_BY_TYPE:
        waiver_type = _WAIVER_BY_TYPE[waiver_type_code]
    else:
        waiver_type = LeagueConfig().waiver_type

    faab_budget = _as_int(settings.get("waiver_budget"))
    if faab_budget is None:
        faab_budget = LeagueConfig().faab_budget

    trade_deadline = _as_int(settings.get("trade_deadline"))
    if trade_deadline is None:
        trade_deadline = LeagueConfig().trade_deadline_week

    playoff_teams = _as_int(settings.get("playoff_teams"))
    if playoff_teams is None:
        playoff_teams = LeagueConfig().playoff_teams

    playoff_start = _as_int(settings.get("playoff_week_start"))
    if playoff_start is None:
        playoff_start = LeagueConfig().playoff_start_week

    league = LeagueConfig(
        league_size=league_size,
        format=league_format,
        scoring=scoring,
        roster=roster,
        waiver_type=waiver_type,
        faab_budget=faab_budget,
        trade_deadline_week=trade_deadline,
        playoff_teams=playoff_teams,
        playoff_start_week=playoff_start,
    )

    median_enabled = _as_int(settings.get("league_average_match")) == 1
    matchup = MatchupFormat(
        style="h2h_median" if median_enabled else "h2h",
        median_enabled=median_enabled,
    )

    playoff_seed_type = _as_int(settings.get("playoff_seed_type"))
    tiebreakers = TiebreakerConfig(
        order=list(_TIEBREAKER_ORDER),
        playoff_seed_type=playoff_seed_type,
    )

    superflex = roster.superflex > 0 or roster.qb >= 2
    te_premium_flag = abs(receiving.te_premium) > _EPS

    coverage = CoverageReport(
        status="partial" if unsupported else "full",
        supported_keys=sorted(supported),
        unsupported_keys=sorted(unsupported.values(), key=lambda item: item.key),
        ignored_zero_keys=sorted(ignored_zero),
    )

    return CompiledRules(
        league_id=str(sleeper_json.get("league_id") or ""),
        name=str(sleeper_json.get("name") or ""),
        season=str(sleeper_json.get("season") or ""),
        league=league,
        matchup=matchup,
        tiebreakers=tiebreakers,
        te_premium=te_premium_flag,
        superflex=superflex,
        best_ball=best_ball,
        coverage=coverage,
    )


def _apply_direct(
    scoring_raw: dict[str, Any],
    mapping: dict[str, str],
    target: BaseModel,
    supported: set[str],
    consumed: set[str],
) -> None:
    for sleeper_key, field_name in mapping.items():
        if sleeper_key not in scoring_raw:
            continue
        value = _as_float(scoring_raw[sleeper_key])
        if value is None:
            continue
        setattr(target, field_name, value)
        supported.add(sleeper_key)
        consumed.add(sleeper_key)


def _apply_te_premium(
    scoring_raw: dict[str, Any],
    receiving: ReceivingRules,
    supported: set[str],
    unsupported: dict[str, UnsupportedScoringKey],
    consumed: set[str],
) -> None:
    has_bonus = "bonus_rec_te" in scoring_raw
    has_rec_te = "rec_te" in scoring_raw

    bonus_val = _as_float(scoring_raw["bonus_rec_te"]) if has_bonus else None
    rec_te_val = _as_float(scoring_raw["rec_te"]) if has_rec_te else None

    if has_bonus and bonus_val is not None:
        consumed.add("bonus_rec_te")
        supported.add("bonus_rec_te")
        receiving.te_premium = bonus_val

    if has_rec_te and rec_te_val is not None:
        consumed.add("rec_te")
        delta = rec_te_val - receiving.rec
        if has_bonus and bonus_val is not None:
            if abs(bonus_val - delta) > _EPS:
                # Apply bonus_rec_te; mark rec_te conflict (partial).
                unsupported["rec_te"] = UnsupportedScoringKey(
                    key="rec_te",
                    value=rec_te_val,
                    reason="conflict",
                )
            else:
                supported.add("rec_te")
        else:
            if delta > _EPS:
                receiving.te_premium = delta
            supported.add("rec_te")


def _apply_yardage_bonuses(
    scoring_raw: dict[str, Any],
    passing: PassingRules,
    rushing: RushingRules,
    receiving: ReceivingRules,
    supported: set[str],
    consumed: set[str],
) -> None:
    sections: dict[str, tuple[BaseModel, str]] = {
        "passing": (passing, "pass_yardage_bonuses"),
        "rushing": (rushing, "rush_yardage_bonuses"),
        "receiving": (receiving, "rec_yardage_bonuses"),
    }

    present_by_section: dict[str, dict[float, tuple[str, float]]] = {
        "passing": {},
        "rushing": {},
        "receiving": {},
    }

    for key, (section, threshold) in _YARDAGE_BONUS_KEYS.items():
        if key not in scoring_raw:
            continue
        value = _as_float(scoring_raw[key])
        if value is None:
            continue
        present_by_section[section][threshold] = (key, value)
        consumed.add(key)
        supported.add(key)

    for section, low_key, high_key in _YARDAGE_PAIRS:
        model, field_name = sections[section]
        defaults: list[YardageBonus] = list(getattr(model, field_name))
        by_threshold = {bonus.threshold: bonus.points for bonus in defaults}
        present = present_by_section[section]
        if not present:
            continue

        low_threshold = _YARDAGE_BONUS_KEYS[low_key][1]
        high_threshold = _YARDAGE_BONUS_KEYS[high_key][1]
        low_present = low_threshold in present
        high_present = high_threshold in present

        if low_present and high_present:
            p_low = present[low_threshold][1]
            p_high = present[high_threshold][1]
            by_threshold[low_threshold] = p_low
            by_threshold[high_threshold] = p_high - p_low
        else:
            for threshold, (_key, points) in present.items():
                by_threshold[threshold] = points

        setattr(
            model,
            field_name,
            [
                YardageBonus(threshold=threshold, points=points)
                for threshold, points in sorted(by_threshold.items())
            ],
        )


def _apply_fg_ranges(
    scoring_raw: dict[str, Any],
    kicking: KickingRules,
    *,
    made: bool,
    supported: set[str],
    unsupported: dict[str, UnsupportedScoringKey],
    consumed: set[str],
) -> None:
    buckets = _FG_MADE_BUCKETS if made else _FG_MISS_BUCKETS
    plus_keys = _FG_MADE_50_KEYS if made else _FG_MISS_50_KEYS
    field_name = "fg_made_ranges" if made else "fg_missed_ranges"

    family_keys = [key for key, _lo, _hi in buckets] + list(plus_keys)
    present_keys = [key for key in family_keys if key in scoring_raw]
    if not present_keys:
        return

    ranges: list[RangeRule] = []
    for key, min_value, max_value in buckets:
        if key in scoring_raw:
            value = _as_float(scoring_raw[key])
            if value is None:
                continue
            ranges.append(RangeRule(min_value=min_value, max_value=max_value, points=value))
            supported.add(key)
            consumed.add(key)
        else:
            # Explicitly supplied family: missing bucket contributes zero.
            ranges.append(RangeRule(min_value=min_value, max_value=max_value, points=0.0))

    plus_present: list[tuple[str, float]] = []
    for key in plus_keys:
        if key not in scoring_raw:
            continue
        value = _as_float(scoring_raw[key])
        if value is None:
            continue
        plus_present.append((key, value))
        consumed.add(key)

    if plus_present:
        values = [value for _key, value in plus_present]
        if max(values) - min(values) > _EPS:
            for key, value in plus_present:
                unsupported[key] = UnsupportedScoringKey(
                    key=key,
                    value=value,
                    reason="exclusive_range_unrepresentable",
                )
            # Family still supplied for lower buckets; 50+ contributes zero.
            ranges.append(RangeRule(min_value=50.0, max_value=None, points=0.0))
        else:
            for key, _value in plus_present:
                supported.add(key)
            ranges.append(RangeRule(min_value=50.0, max_value=None, points=values[0]))
    else:
        ranges.append(RangeRule(min_value=50.0, max_value=None, points=0.0))

    setattr(kicking, field_name, ranges)


def _apply_defense_and_fum_rec(
    scoring_raw: dict[str, Any],
    defense: DefenseRules,
    misc: MiscRules,
    *,
    def_rostered: bool,
    supported: set[str],
    unsupported: dict[str, UnsupportedScoringKey],
    consumed: set[str],
) -> None:
    # Points-allowed family (DEF only)
    pts_keys = [key for key, _lo, _hi in _PTS_ALLOW_BUCKETS]
    pts_present = [key for key in pts_keys if key in scoring_raw]
    if pts_present:
        if def_rostered:
            ranges: list[RangeRule] = []
            for key, min_value, max_value in _PTS_ALLOW_BUCKETS:
                if key in scoring_raw:
                    value = _as_float(scoring_raw[key])
                    if value is None:
                        continue
                    ranges.append(
                        RangeRule(min_value=min_value, max_value=max_value, points=value)
                    )
                    supported.add(key)
                    consumed.add(key)
                else:
                    ranges.append(RangeRule(min_value=min_value, max_value=max_value, points=0.0))
            defense.points_allowed_ranges = ranges
        else:
            for key in pts_present:
                value = _as_float(scoring_raw[key])
                if value is None:
                    continue
                if abs(value) > _EPS:
                    unsupported[key] = UnsupportedScoringKey(
                        key=key, value=value, reason="unmapped"
                    )
                    consumed.add(key)

    # Scalar DST keys
    dst_scalar_keys = (
        "sack",
        "int",
        "def_td",
        "safe",
        "blk_kick",
        "ff",
        "tkl_loss",
        "qb_hit",
    )
    for key in dst_scalar_keys:
        if key not in scoring_raw:
            continue
        value = _as_float(scoring_raw[key])
        if value is None:
            continue
        field_name = _DEFENSE_DIRECT[key]
        if def_rostered:
            setattr(defense, field_name, value)
            supported.add(key)
            consumed.add(key)
        # else: leave for leftover (unmapped / ignored_zero)

    # fum_rec / fum_rec_td
    for key, misc_field, def_field in (
        ("fum_rec", "fumble_rec", "fumble_recovery"),
        ("fum_rec_td", "fumble_rec_td", "td"),
    ):
        if key not in scoring_raw:
            continue
        value = _as_float(scoring_raw[key])
        if value is None:
            continue
        if def_rostered:
            if key == "fum_rec_td" and "def_td" in scoring_raw:
                def_td_val = _as_float(scoring_raw["def_td"])
                if def_td_val is not None and abs(def_td_val - value) > _EPS:
                    # def_td already applied to defense.td; conflicting fum_rec_td.
                    unsupported[key] = UnsupportedScoringKey(
                        key=key, value=value, reason="conflict"
                    )
                    consumed.add(key)
                    continue
            setattr(defense, def_field, value)
            supported.add(key)
            consumed.add(key)
        else:
            setattr(misc, misc_field, value)
            supported.add(key)
            consumed.add(key)


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
        field = _ROSTER_SLOT_MAP.get(slot)
        if field is not None:
            counts[field] += 1

    return RosterConfig(**counts)


def _compile_format(settings: dict[str, Any]) -> tuple[LeagueFormat, bool]:
    best_ball = _as_int(settings.get("best_ball")) == 1
    if best_ball:
        return "best_ball", True
    league_type = _as_int(settings.get("type"))
    if league_type in _FORMAT_BY_TYPE:
        return _FORMAT_BY_TYPE[league_type], False
    return LeagueConfig().format, False


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
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
