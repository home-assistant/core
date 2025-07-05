"""Test Wallbox Init Component."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    http_403_error,
    http_429_error,
    setup_integration,
    test_response_no_power_boost,
)

from tests.common import MockConfigEntry


async def test_wallbox_setup_unload_entry(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_unload_entry_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload Connection Error."""
    with patch.object(mock_wallbox, "authenticate", side_effect=http_403_error):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.SETUP_ERROR

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error_auth(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "authenticate", side_effect=http_429_error):
        wallbox = entry.runtime_data
        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_invalid_auth(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with (
        patch.object(mock_wallbox, "authenticate", side_effect=http_403_error),
        patch.object(mock_wallbox, "pauseChargingSession", side_effect=http_403_error),
    ):
        wallbox = entry.runtime_data

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_http_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_403_error):
        wallbox = entry.runtime_data

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_too_many_requests(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_429_error):
        wallbox = entry.runtime_data

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "pauseChargingSession", side_effect=http_403_error):
        wallbox = entry.runtime_data

        await wallbox.async_refresh()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_setup_load_entry_no_eco_mode(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload."""
    with patch.object(
        mock_wallbox, "getChargerStatus", return_value=test_response_no_power_boost
    ):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
