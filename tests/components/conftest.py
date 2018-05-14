"""Fixtures for component testing."""
import pytest

from homeassistant.setup import async_setup_component

from tests.common import MockUser


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


@pytest.fixture
def hass_access_token(hass):
    """Return an access token to access Home Assistant."""
    user = MockUser().add_to_hass(hass)
    client = hass.loop.run_until_complete(hass.auth.async_create_client(
        'Access Token Fixture',
        redirect_uris=['/'],
        no_secret=True,
    ))
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(user, client.id))
    yield hass.auth.async_create_access_token(refresh_token)
