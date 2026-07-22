from pydantic import BaseModel, ConfigDict


class ScreenerRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gsis_id: str
    name: str
    position: str
    team: str | None = None
    games: int
    pass_att: float
    pass_cmp: float
    pass_yd: float
    pass_td: float
    pass_int: float
    rush_att: float
    rush_yd: float
    rush_td: float
    target: float
    rec: float
    rec_yd: float
    rec_td: float
    fumble_lost: float
    fantasy_points: float = 0.0


class ScreenerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int
    total: int
    rows: list[ScreenerRow]
