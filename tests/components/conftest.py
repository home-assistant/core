"""Fixtures for component testing."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.http import URL
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH, TYPE_AUTH_OK, TYPE_AUTH_REQUIRED)

from tests.common import mock_coro


@pytest.fixture(autouse=True)
def prevent_io():
    """Fixture to prevent certain I/O from happening."""
    with patch('homeassistant.components.http.ban.async_load_ip_bans_config',
               side_effect=lambda *args: mock_coro([])):
        yield


@pytest.fixture
def hass_ws_client(aiohttp_client, hass_access_token):
    """Websocket client fixture connected to websocket server."""
    async def create_client(hass, access_token=hass_access_token):
        """Create a websocket client."""
        assert await async_setup_component(hass, 'websocket_api')

        client = await aiohttp_client(hass.http.app)

        with patch('homeassistant.components.http.auth.setup_auth'):
            websocket = await client.ws_connect(URL)
            auth_resp = await websocket.receive_json()
            assert auth_resp['type'] == TYPE_AUTH_REQUIRED

            if access_token is None:
                await websocket.send_json({
                    'type': TYPE_AUTH,
                    'api_password': 'bla'
                })
            else:
                await websocket.send_json({
                    'type': TYPE_AUTH,
                    'access_token': access_token
                })

            auth_ok = await websocket.receive_json()
            assert auth_ok['type'] == TYPE_AUTH_OK

        # wrap in client
        websocket.client = client
        return websocket

    return create_client
