"""Test Mikrotik setup process."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from librouteros.exceptions import ConnectionClosed, LibRouterosError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import async_fire_time_changed


async def test_successful_config_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test config entry successful setup."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED


async def test_hub_connection_error(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry
) -> None:
    """Test setup fails due to connection error."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_authentication_error(
    hass: HomeAssistant, mock_api: MagicMock, mock_config_entry
) -> None:
    """Test setup fails due to authentication error."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    mock_api.side_effect = LibRouterosError("invalid user name or password")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_connection_lost_during_refresh_raises_update_failed(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test a lost connection during a scheduled refresh is treated as UpdateFailed.

    ConfigEntryNotReady is only special-cased on the first refresh; raising
    it from later scheduled refreshes falls through to the coordinator's
    generic exception handler instead of the dedicated UpdateFailed one.
    """
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})
    assert entry.state is ConfigEntryState.LOADED

    coordinator = entry.runtime_data

    with patch.object(
        entry.runtime_data.api,
        "command",
        side_effect=OSError(113, "Host is unreachable"),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_unload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading an entry."""
    entry = mock_config_entry()
    await setup_integration(hass, entry, command_responses={})

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
