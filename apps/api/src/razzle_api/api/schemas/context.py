"""Request/response models for the context kernel."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from razzle_api.api.schemas.provenance import ProvenanceMeta
from razzle_api.domain.scoring import CompiledRules, CoverageReport


class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(min_length=1)


class UserIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    username: str
    display_name: str | None = None
    avatar: str | None = None


class LeagueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    league_id: str
    name: str
    season: int
    sport: str = "nfl"
    total_rosters: int | None = None


class ConnectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: UserIdentity
    season: int
    leagues: list[LeagueSummary]
    meta: ProvenanceMeta


class ContextRevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    league_id: str
    season: int
    created_at: datetime
    league: dict[str, Any]
    users: list[dict[str, Any]]
    rosters: list[dict[str, Any]]
    matchups_by_week: dict[int, list[dict[str, Any]]]
    transactions_by_week: dict[int, list[dict[str, Any]]]
    traded_picks: list[dict[str, Any]]
    state: dict[str, Any]
    compiled_rules: CompiledRules
    coverage: CoverageReport
    meta: ProvenanceMeta
