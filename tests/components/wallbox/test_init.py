"""Test Wallbox Init Component."""
import json

import requests_mock

from homeassistant.components.wallbox import CONF_MAX_CHARGING_CURRENT_KEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import test_response

from tests.components.wallbox import (
    DOMAIN,
    entry,
    setup_integration,
    setup_integration_connection_error,
    setup_integration_read_only,
)
from tests.components.wallbox.const import (
    CONF_ERROR,
    CONF_JWT,
    CONF_STATUS,
    CONF_TTL,
    CONF_USER_ID,
)

authorisation_response = json.loads(
    json.dumps(
        {
            CONF_JWT: "fakekeyhere",
            CONF_USER_ID: 12345,
            CONF_TTL: 145656758,
            CONF_ERROR: "false",
            CONF_STATUS: 200,
        }
    )
)


async def test_wallbox_setup_unload_entry(hass: HomeAssistant):
    """Test Wallbox Unload."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_unload_entry_connection_error(hass: HomeAssistant):
    """Test Wallbox Unload Connection Error."""

    await setup_integration_connection_error(hass)
    assert entry.state == ConfigEntryState.SETUP_ERROR

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_invalid_auth(hass: HomeAssistant):
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=403,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json=json.loads(json.dumps({CONF_MAX_CHARGING_CURRENT_KEY: 20})),
            status_code=403,
        )

        wallbox = hass.data[DOMAIN][entry.entry_id]

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error(hass: HomeAssistant):
    """Test Wallbox setup with connection error."""

    await setup_integration(hass)
    assert entry.state == ConfigEntryState.LOADED

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://api.wall-box.com/auth/token/user",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response,
            status_code=403,
        )

        wallbox = hass.data[DOMAIN][entry.entry_id]

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_read_only(hass: HomeAssistant):
    """Test Wallbox setup for read-only user."""

    await setup_integration_read_only(hass)
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED
