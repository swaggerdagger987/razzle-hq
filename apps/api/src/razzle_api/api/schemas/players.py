from pydantic import BaseModel, ConfigDict


class PlayerOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gsis_id: str
    name: str
    position: str
    team: str | None = None


class PlayersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    players: list[PlayerOut]
