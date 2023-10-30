"""The tests for http static files."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def http(hass):
    """Ensure http is set up."""
    assert await async_setup_component(
        hass,
        "frontend",
        {},
    )


@pytest.fixture
def aiohttp_client(event_loop, aiohttp_client, socket_enabled):
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client


@pytest.fixture
async def mock_http_client(hass, aiohttp_client):
    """Start the Home Assistant HTTP component."""
    return await aiohttp_client(hass.http.app)


async def test_static_path_cache(hass: HomeAssistant, mock_http_client) -> None:
    """Test static paths cache."""
    resp = await mock_http_client.get("/lovelace/default_view", allow_redirects=False)
    assert resp.status == 404

    resp = await mock_http_client.get("/frontend_latest/", allow_redirects=False)
    assert resp.status == 403

    resp = await mock_http_client.get(
        "/static/icons/favicon.ico", allow_redirects=False
    )
    assert resp.status == 200

    # and again to make sure the cache works
    resp = await mock_http_client.get(
        "/static/icons/favicon.ico", allow_redirects=False
    )
    assert resp.status == 200

    resp = await mock_http_client.get(
        "/static/fonts/roboto/Roboto-Bold.woff2", allow_redirects=False
    )
    assert resp.status == 200

    resp = await mock_http_client.get("/static/does-not-exist", allow_redirects=False)
    assert resp.status == 404

    # and again to make sure the cache works
    resp = await mock_http_client.get("/static/does-not-exist", allow_redirects=False)
    assert resp.status == 404
