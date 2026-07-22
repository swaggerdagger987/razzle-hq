from pydantic import BaseModel, ConfigDict


class WeekStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: int
    pass_att: float
    pass_cmp: float
    pass_yd: float
    pass_td: float
    pass_int: float
    pass_sack: float
    pass_two_pt: float
    rush_att: float
    rush_yd: float
    rush_td: float
    rush_two_pt: float
    target: float
    rec: float
    rec_yd: float
    rec_td: float
    rec_two_pt: float
    fumble: float
    fumble_lost: float
    return_yd: float
    return_td: float
    special_teams_td: float
    pat_made: float
    pat_missed: float
    fg_made: float
    fg_missed: float


class PlayerSeason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int
    week_stats: list[WeekStats]


class PlayerDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gsis_id: str
    name: str
    position: str
    team: str | None = None
    seasons: list[PlayerSeason]


class AdjacentPlayers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prev_gsis_id: str | None = None
    next_gsis_id: str | None = None
