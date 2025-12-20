"""Test the Actron Air coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from actron_neo_api import ActronAirAuthError
from freezegun import freeze_time

from homeassistant.components.actron_air.coordinator import STALE_DEVICE_TIMEOUT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update_auth_error(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator handles authentication error during update."""
    # Setup integration first
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Now make the update fail with auth error
    mock_actron_api.update_status = AsyncMock(
        side_effect=ActronAirAuthError("Auth failed")
    )

    # Trigger an update
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    # After auth error during update, the error is raised and will trigger reauthentication flow
    # The coordinator logs the error but config entry will eventually be marked for reauth
    # For now just verify the update was attempted
    mock_actron_api.update_status.assert_called()


async def test_coordinator_update_general_error(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator handles general errors gracefully."""
    # Setup integration first
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Now make the update fail with general exception
    mock_actron_api.update_status = AsyncMock(side_effect=Exception("Connection error"))

    # Trigger an update
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    # Config entry should still be loaded (UpdateFailed doesn't change entry state)
    assert mock_config_entry.state is ConfigEntryState.LOADED


@freeze_time("2025-01-01 12:00:00")
async def test_coordinator_is_device_stale_false(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test is_device_stale returns False when device is not stale."""
    # Setup integration
    await setup_integration(hass, mock_config_entry)

    # Get the coordinator from runtime_data
    coordinator = mock_config_entry.runtime_data.system_coordinators["123456"]

    # Device should not be stale immediately after setup
    assert not coordinator.is_device_stale()


@freeze_time("2025-01-01 12:00:00")
async def test_coordinator_is_device_stale_true(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test is_device_stale returns True when device is stale."""
    # Setup integration
    await setup_integration(hass, mock_config_entry)

    # Get the coordinator from runtime_data
    coordinator = mock_config_entry.runtime_data.system_coordinators["123456"]

    # Manually set last_seen to more than STALE_DEVICE_TIMEOUT ago
    coordinator.last_seen = (
        dt_util.utcnow() - STALE_DEVICE_TIMEOUT - timedelta(seconds=1)
    )

    # Device should now be stale
    assert coordinator.is_device_stale()
