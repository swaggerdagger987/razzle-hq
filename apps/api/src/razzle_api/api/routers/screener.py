import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from razzle_api.api.schemas.screener import ScreenerResponse, ScreenerRow
from razzle_api.core.db import get_session
from razzle_api.domain.scoring import presets as scoring_presets
from razzle_api.domain.scoring.config import ScoringRules
from razzle_api.services.screener_service import FantasySortTooLargeError, list_season_totals

router = APIRouter(prefix="/api", tags=["screener"])

_SORT_LITERAL = Literal[
    "name",
    "games",
    "fantasy_points",
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
    "fumble_lost",
]

_POSITION_LITERAL = Literal["QB", "RB", "WR", "TE"]

_PRESET_LITERAL = Literal["standard", "PPR", "half", "TEP"]

_PRESET_MAP = {
    "standard": scoring_presets.standard,
    "PPR": scoring_presets.ppr,
    "half": scoring_presets.half_ppr,
    "TEP": scoring_presets.tight_end_premium,
}

# Flat numeric overrides backed by stored week-stat fields + te_premium.
_FLAT_KEY_MAP: dict[str, tuple[str, str]] = {
    "pass_att": ("passing", "pass_att"),
    "pass_cmp": ("passing", "pass_cmp"),
    "pass_yd": ("passing", "pass_yd"),
    "pass_td": ("passing", "pass_td"),
    "pass_int": ("passing", "pass_int"),
    "pass_sack": ("passing", "pass_sack"),
    "pass_two_pt": ("passing", "pass_two_pt"),
    "rush_att": ("rushing", "rush_att"),
    "rush_yd": ("rushing", "rush_yd"),
    "rush_td": ("rushing", "rush_td"),
    "rush_two_pt": ("rushing", "rush_two_pt"),
    "target": ("receiving", "target"),
    "rec": ("receiving", "rec"),
    "rec_yd": ("receiving", "rec_yd"),
    "rec_td": ("receiving", "rec_td"),
    "rec_two_pt": ("receiving", "rec_two_pt"),
    "te_premium": ("receiving", "te_premium"),
    "fumble": ("misc", "fumble"),
    "fumble_lost": ("misc", "fumble_lost"),
    "return_yd": ("misc", "return_yd"),
    "return_td": ("misc", "return_td"),
    "special_teams_td": ("misc", "special_teams_td"),
    "pat_made": ("kicking", "pat_made"),
    "pat_missed": ("kicking", "pat_missed"),
    "fg_made": ("kicking", "fg_made"),
    "fg_missed": ("kicking", "fg_missed"),
}


def _resolve_scoring_rules(
    scoring_preset: str,
    scoring_rules_json: str | None,
) -> ScoringRules:
    """Resolve ScoringRules from preset + optional flat numeric overrides.

    Rejects invalid JSON, non-objects, unknown keys, nonnumeric values, and
    nested submodels. Never silently ignores a rule.
    """
    league_config = _PRESET_MAP[scoring_preset]()
    rules = league_config.scoring

    if not scoring_rules_json:
        return rules

    try:
        overrides = json.loads(scoring_rules_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"scoring_rules is not valid JSON: {exc}",
        ) from exc

    if not isinstance(overrides, dict):
        raise HTTPException(status_code=422, detail="scoring_rules must be a JSON object")

    rules_dict = rules.model_dump()

    for key, value in overrides.items():
        if key not in _FLAT_KEY_MAP:
            raise HTTPException(
                status_code=422,
                detail=f"unknown scoring_rules key: {key}",
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(
                status_code=422,
                detail=f"scoring_rules.{key} must be numeric",
            )
        sub_model, field = _FLAT_KEY_MAP[key]
        rules_dict[sub_model][field] = float(value)

    return ScoringRules.model_validate(rules_dict)


@router.get("/screener", response_model=ScreenerResponse)
async def get_screener(
    session: Annotated[Session, Depends(get_session)],
    season: Annotated[int, Query(ge=2000, le=2100)] = 2025,
    position: Annotated[_POSITION_LITERAL | None, Query()] = None,
    sort: Annotated[_SORT_LITERAL, Query()] = "name",
    dir: Annotated[Literal["asc", "desc"], Query()] = "asc",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    scoring_preset: Annotated[_PRESET_LITERAL, Query()] = "standard",
    scoring_rules: Annotated[str | None, Query()] = None,
) -> ScreenerResponse:
    descending = dir == "desc"
    active_rules = _resolve_scoring_rules(scoring_preset, scoring_rules)

    try:
        rows, total = list_season_totals(
            session,
            season=season,
            position=position,
            sort=sort,
            descending=descending,
            limit=limit,
            offset=offset,
            scoring_rules=active_rules,
        )
    except FantasySortTooLargeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ScreenerResponse(
        season=season,
        total=total,
        rows=[ScreenerRow(**row) for row in rows],
    )
