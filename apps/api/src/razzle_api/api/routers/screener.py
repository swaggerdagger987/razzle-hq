import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from razzle_api.api.schemas.screener import ScreenerResponse, ScreenerRow
from razzle_api.core.db import get_session
from razzle_api.domain.scoring import presets as scoring_presets
from razzle_api.domain.scoring.config import ScoringRules
from razzle_api.services.screener_service import list_season_totals

router = APIRouter(prefix="/api", tags=["screener"])

# Valid sort values: "name", "games", "fantasy_points", plus the 13 stat aggregation columns.
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


def _resolve_scoring_rules(
    scoring_preset: str,
    scoring_rules_json: str | None,
) -> ScoringRules:
    """Resolve the final ScoringRules from preset + optional JSON override.

    If scoring_rules_json is provided, parse it as a partial ScoringRules
    dict and merge on top of the preset. The JSON may override any top-level
    ScoringRules field (passing, rushing, receiving, misc, kicking, defense,
    idp) or specific scalar sub-fields like {"pass_td": 6}.

    For simplicity at L3 MVP we support a flat dict of scalar overrides on the
    top-level sub-models (e.g. {"pass_td": 6, "rec": 1, "rush_yd": 0.1}).
    """
    league_config = _PRESET_MAP[scoring_preset]()
    rules = league_config.scoring

    if not scoring_rules_json:
        return rules

    try:
        overrides: dict = json.loads(scoring_rules_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"scoring_rules is not valid JSON: {exc}",
        ) from exc

    if not isinstance(overrides, dict):
        raise HTTPException(status_code=422, detail="scoring_rules must be a JSON object")

    # Build a merged dict from the rules model and apply scalar overrides.
    rules_dict = rules.model_dump()

    # Map flat override keys to their sub-model.
    _flat_key_map: dict[str, tuple[str, str]] = {
        # passing
        "pass_yd": ("passing", "pass_yd"),
        "pass_td": ("passing", "pass_td"),
        "pass_int": ("passing", "pass_int"),
        "pass_two_pt": ("passing", "pass_two_pt"),
        "pass_att": ("passing", "pass_att"),
        "pass_cmp": ("passing", "pass_cmp"),
        # rushing
        "rush_yd": ("rushing", "rush_yd"),
        "rush_td": ("rushing", "rush_td"),
        "rush_two_pt": ("rushing", "rush_two_pt"),
        # receiving
        "rec": ("receiving", "rec"),
        "rec_yd": ("receiving", "rec_yd"),
        "rec_td": ("receiving", "rec_td"),
        "rec_two_pt": ("receiving", "rec_two_pt"),
        "te_premium": ("receiving", "te_premium"),
        # misc
        "fumble_lost": ("misc", "fumble_lost"),
        "fumble": ("misc", "fumble"),
    }

    for key, value in overrides.items():
        if key in _flat_key_map:
            sub_model, field = _flat_key_map[key]
            rules_dict[sub_model][field] = float(value)
        elif key in rules_dict:
            # Allow full sub-model dict overrides too.
            if isinstance(value, dict) and isinstance(rules_dict[key], dict):
                rules_dict[key].update(value)

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
    # Default sort direction: asc for name, desc for numeric columns.
    descending = dir == "desc"

    active_rules = _resolve_scoring_rules(scoring_preset, scoring_rules)

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
    return ScreenerResponse(
        season=season,
        total=total,
        rows=[ScreenerRow(**row) for row in rows],
    )
