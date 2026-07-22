from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from razzle_api.api.routers.context import router as context_router
from razzle_api.api.routers.health import router as health_router
from razzle_api.api.routers.line import router as line_router
from razzle_api.api.routers.me import router as me_router
from razzle_api.api.routers.players import router as players_router
from razzle_api.api.routers.players_detail import router as players_detail_router
from razzle_api.api.routers.scenarios import router as scenarios_router
from razzle_api.api.routers.scoring import router as scoring_router
from razzle_api.api.routers.scratchpad import router as scratchpad_router
from razzle_api.api.routers.screener import router as screener_router
from razzle_api.api.routers.valuation import router as valuation_router
from razzle_api.api.routers.values import router as values_router
from razzle_api.api.routers.war_room import router as war_room_router
from razzle_api.config import get_settings
from razzle_api.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.environment)
    app = FastAPI(title="Razzle API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(players_router)
    app.include_router(players_detail_router)
    app.include_router(screener_router)
    app.include_router(scoring_router)
    app.include_router(valuation_router)
    app.include_router(context_router)
    app.include_router(me_router)
    app.include_router(scenarios_router)
    app.include_router(scratchpad_router)
    app.include_router(line_router)
    app.include_router(war_room_router)
    app.include_router(values_router)
    return app


app = create_app()
