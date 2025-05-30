"""Test Wallbox Init Component."""

import requests_mock

from homeassistant.components.wallbox.const import (
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    authorisation_response,
    setup_integration,
    setup_integration_connection_error,
    setup_integration_read_only,
    test_response,
)

from tests.common import MockConfigEntry


async def test_wallbox_setup_unload_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test Wallbox Unload."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_unload_entry_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test Wallbox Unload Connection Error."""

    await setup_integration_connection_error(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error_auth(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=404,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response,
            status_code=200,
        )

        wallbox = hass.data[DOMAIN][entry.entry_id]

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_invalid_auth(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=403,
        )
        mock_request.put(
            "https://api.wall-box.com/v2/charger/12345",
            json={CHARGER_MAX_CHARGING_CURRENT_KEY: 20},
            status_code=403,
        )

        wallbox = hass.data[DOMAIN][entry.entry_id]

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
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
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_read_only(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test Wallbox setup for read-only user."""

    await setup_integration_read_only(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
