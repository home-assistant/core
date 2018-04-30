"""Fixtures for component testing."""
import pytest

from homeassistant.setup import async_setup_component


@pytest.fixture
def hass_ws_client(aiohttp_client):
    """Websocket client fixture connected to websocket server."""
    async def create_client(hass):
        """Create a websocket client."""
        wapi = hass.components.websocket_api
        assert await async_setup_component(hass, 'websocket_api')

        client = await aiohttp_client(hass.http.app)
        websocket = await client.ws_connect(wapi.URL)
        auth_ok = await websocket.receive_json()
        assert auth_ok['type'] == wapi.TYPE_AUTH_OK

        return websocket

    return create_client
