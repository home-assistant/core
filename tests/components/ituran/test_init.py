"""Tests for the Ituran integration."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyituran.exceptions import IturanApiError, IturanAuthError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ituran.const import UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ituran: AsyncMock,
) -> None:
    """Test the Ituran configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ituran: AsyncMock,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device information."""
    await setup_integration(hass, mock_config_entry)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries == snapshot


async def test_remove_stale_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ituran: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that devices not returned by the service are removed."""
    await setup_integration(hass, mock_config_entry)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1

    mock_ituran.get_vehicles.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 0


async def test_recover_from_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ituran: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify we can recover from service Errors."""

    await setup_integration(hass, mock_config_entry)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1

    mock_ituran.get_vehicles.side_effect = IturanApiError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1
    assert not mock_config_entry.runtime_data.last_update_success

    mock_ituran.get_vehicles.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.last_update_success

    # An auth error stops polling until the user reauthenticates
    mock_ituran.get_vehicles.side_effect = IturanAuthError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1
    assert not mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
