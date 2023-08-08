"""Test headers middleware."""
from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http.headers import setup_headers

from tests.typing import ClientSessionGenerator


async def mock_handler(request):
    """Return OK."""
    return web.Response(text="OK")


async def test_headers_added(aiohttp_client: ClientSessionGenerator) -> None:
    """Test that headers are being added on each request."""
    app = web.Application()
    app.router.add_get("/", mock_handler)

    setup_headers(app, use_x_frame_options=True)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/")

    assert resp.status == HTTPStatus.OK
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Server"] == ""
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "SAMEORIGIN"


async def test_allow_framing(aiohttp_client: ClientSessionGenerator) -> None:
    """Test that we allow framing when disabled."""
    app = web.Application()
    app.router.add_get("/", mock_handler)

    setup_headers(app, use_x_frame_options=False)

    mock_api_client = await aiohttp_client(app)
    resp = await mock_api_client.get("/")

    assert resp.status == HTTPStatus.OK
    assert "X-Frame-Options" not in resp.headers
