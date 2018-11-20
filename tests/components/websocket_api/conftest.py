"""Fixtures for websocket tests."""
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.http import URL
from homeassistant.components.websocket_api.auth import TYPE_AUTH_REQUIRED

from . import API_PASSWORD


@pytest.fixture
def websocket_client(hass, hass_ws_client):
    """Create a websocket client."""
    return hass.loop.run_until_complete(hass_ws_client(hass))


@pytest.fixture
def no_auth_websocket_client(hass, loop, aiohttp_client):
    """Websocket connection that requires authentication."""
    assert loop.run_until_complete(
        async_setup_component(hass, 'websocket_api', {
            'http': {
                'api_password': API_PASSWORD
            }
        }))

    client = loop.run_until_complete(aiohttp_client(hass.http.app))
    ws = loop.run_until_complete(client.ws_connect(URL))

    auth_ok = loop.run_until_complete(ws.receive_json())
    assert auth_ok['type'] == TYPE_AUTH_REQUIRED

    yield ws

    if not ws.closed:
        loop.run_until_complete(ws.close())
