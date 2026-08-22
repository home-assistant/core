"""Tests for the HTTP helpers."""

from http import HTTPStatus

from aiohttp import web
import pytest

from homeassistant.helpers.http import MIN_COMPRESSED_RESPONSE_SIZE, HomeAssistantView

from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("body_size", "expect_compression"),
    [
        pytest.param(8, False, id="small-body-not-compressed"),
        pytest.param(
            MIN_COMPRESSED_RESPONSE_SIZE * 2, True, id="large-body-compressed"
        ),
    ],
)
@pytest.mark.usefixtures("socket_enabled")
async def test_json_response_compression_threshold(
    aiohttp_client: ClientSessionGenerator,
    body_size: int,
    expect_compression: bool,
) -> None:
    """Test HomeAssistantView.json only compresses bodies above the threshold."""

    async def handler(request: web.Request) -> web.Response:
        return HomeAssistantView.json({"data": "x" * body_size})

    app = web.Application()
    app.router.add_get("/", handler)
    client = await aiohttp_client(app)

    resp = await client.get("/", headers={"Accept-Encoding": "gzip, deflate"})

    assert resp.status == HTTPStatus.OK
    assert ("Content-Encoding" in resp.headers) is expect_compression
