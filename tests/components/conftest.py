"""Fixtures for component testing."""
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import websocket_api

from tests.common import MockUser, CLIENT_ID


@pytest.fixture
def hass_ws_client(aiohttp_client):
    """Websocket client fixture connected to websocket server."""
    async def create_client(hass, access_token=None):
        """Create a websocket client."""
        wapi = hass.components.websocket_api
        assert await async_setup_component(hass, 'websocket_api')

        client = await aiohttp_client(hass.http.app)
        websocket = await client.ws_connect(wapi.URL)
        auth_resp = await websocket.receive_json()

        if auth_resp['type'] == wapi.TYPE_AUTH_OK:
            assert access_token is None, \
                'Access token given but no auth required'
            return websocket

        assert access_token is not None, 'Access token required for fixture'

        await websocket.send_json({
            'type': websocket_api.TYPE_AUTH,
            'access_token': access_token
        })

        auth_ok = await websocket.receive_json()
        assert auth_ok['type'] == wapi.TYPE_AUTH_OK

        return websocket

    return create_client


@pytest.fixture
def hass_access_token(hass):
    """Return an access token to access Home Assistant."""
    user = MockUser().add_to_hass(hass)
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(user, CLIENT_ID))
    yield hass.auth.async_create_access_token(refresh_token)
