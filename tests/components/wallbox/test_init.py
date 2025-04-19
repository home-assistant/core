"""Test Wallbox Init Component."""

from unittest.mock import Mock, patch

from homeassistant.components.wallbox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    authorisation_response,
    http_403_error,
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

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(side_effect=http_403_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.pauseChargingSession",
            new=Mock(return_value=test_response),
        ),
    ):
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

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(side_effect=http_403_error),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.pauseChargingSession",
            new=Mock(side_effect=http_403_error),
        ),
    ):
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

    with (
        patch(
            "homeassistant.components.wallbox.Wallbox.authenticate",
            new=Mock(return_value=authorisation_response),
        ),
        patch(
            "homeassistant.components.wallbox.Wallbox.pauseChargingSession",
            new=Mock(side_effect=http_403_error),
        ),
    ):
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
