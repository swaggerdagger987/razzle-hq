from httpx import ASGITransport, AsyncClient

from razzle_api.api.routers.line import router as line_router
from razzle_api.api.routers.scratchpad import router as scratchpad_router
from razzle_api.api.routers.values import router as values_router
from razzle_api.api.routers.war_room import router as war_room_router
from razzle_api.main import app

FROZEN_METHODS = {
    "/api/context/connect": "post",
    "/api/context/leagues/{league_id}/refresh": "post",
    "/api/context/revision/{revision_id}": "get",
    "/api/me": "get",
    "/api/scenarios": "post",
}


def test_frozen_context_paths_and_existing_routes_are_in_openapi() -> None:
    paths = app.openapi()["paths"]

    for path, method in FROZEN_METHODS.items():
        assert path in paths
        assert method in paths[path]

    assert "get" in paths["/health"]
    assert "get" in paths["/api/players"]
    assert "get" in paths["/api/screener"]
    assert "post" in paths["/scoring/preview"]
    assert "post" in paths["/valuation/vorp/preview"]


def test_empty_room_routers_hold_their_final_prefixes() -> None:
    assert scratchpad_router.prefix == "/api/scratchpad"
    assert line_router.prefix == "/api/line"
    assert war_room_router.prefix == "/api/war-room"
    assert values_router.prefix == "/api/values"


async def test_remaining_preregistered_stubs_return_explicit_501() -> None:
    requests = (
        ("GET", "/api/me", None),
        ("POST", "/api/scenarios", {}),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for method, path, body in requests:
            response = await client.request(method, path, json=body)
            assert response.status_code == 501
            assert response.json() == {"detail": "not implemented"}

        health = await client.get("/health")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
