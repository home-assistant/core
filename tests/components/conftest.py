"""Fixtures for component testing."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.websocket_api.http import URL
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH, TYPE_AUTH_OK, TYPE_AUTH_REQUIRED)

from tests.common import MockUser, CLIENT_ID


@pytest.fixture
def hass_ws_client(aiohttp_client):
    """Websocket client fixture connected to websocket server."""
    async def create_client(hass, access_token=None):
        """Create a websocket client."""
        assert await async_setup_component(hass, 'websocket_api')

        client = await aiohttp_client(hass.http.app)

        patches = []

        if access_token is None:
            patches.append(patch(
                'homeassistant.auth.AuthManager.active', return_value=False))
            patches.append(patch(
                'homeassistant.auth.AuthManager.support_legacy',
                return_value=True))
            patches.append(patch(
                'homeassistant.components.websocket_api.auth.'
                'validate_password', return_value=True))
        else:
            patches.append(patch(
                'homeassistant.auth.AuthManager.active', return_value=True))
            patches.append(patch(
                'homeassistant.components.http.auth.setup_auth'))

        for p in patches:
            p.start()

        try:
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

        finally:
            for p in patches:
                p.stop()

        # wrap in client
        websocket.client = client
        return websocket

    return create_client


@pytest.fixture
def hass_access_token(hass):
    """Return an access token to access Home Assistant."""
    user = MockUser().add_to_hass(hass)
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(user, CLIENT_ID))
    yield hass.auth.async_create_access_token(refresh_token)
