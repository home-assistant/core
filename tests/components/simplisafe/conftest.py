"""Define test fixtures for SimpliSafe."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.simplisafe.config_flow import CONF_AUTH_CODE
from homeassistant.components.simplisafe.const import CONF_USER_ID, DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

REFRESH_TOKEN = "token123"
USER_ID = "12345"


@pytest.fixture(name="api")
def api_fixture(websocket):
    """Define a fixture for a simplisafe-python API object."""
    return Mock(
        async_get_systems=AsyncMock(),
        refresh_token=REFRESH_TOKEN,
        user_id=USER_ID,
        websocket=websocket,
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=USER_ID, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_USER_ID: USER_ID,
        CONF_TOKEN: REFRESH_TOKEN,
    }


@pytest.fixture(name="config_code")
def config_code_fixture(hass):
    """Define a authorization code."""
    return {
        CONF_AUTH_CODE: "code123",
    }


@pytest.fixture(name="setup_simplisafe")
async def setup_simplisafe_fixture(hass, api, config):
    """Define a fixture to set up SimpliSafe."""
    with patch(
        "homeassistant.components.simplisafe.API.async_from_auth", return_value=api
    ), patch(
        "homeassistant.components.simplisafe.API.async_from_refresh_token",
        return_value=api,
    ), patch(
        "homeassistant.components.simplisafe.SimpliSafe.async_init"
    ), patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
        return_value=api,
    ), patch(
        "homeassistant.components.simplisafe.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="websocket")
def websocket_fixture():
    """Define a fixture for a simplisafe-python websocket object."""
    return Mock(
        async_connect=AsyncMock(),
        async_disconnect=AsyncMock(),
        async_listen=AsyncMock(),
    )
