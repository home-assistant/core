"""Tests for the IPP integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyipp import IPPConnectionError
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ipp.const import REQUEST_TIMEOUT
from homeassistant.components.ipp.coordinator import (
    SCAN_INTERVAL,
    IPPDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@patch(
    "homeassistant.components.ipp.coordinator.IPP._request",
    side_effect=IPPConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the IPP configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
) -> None:
    """Test the IPP configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, IPPDataUpdateCoordinator)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_request_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a printer gets time to wake up before we give up on it."""
    coordinator = IPPDataUpdateCoordinator(hass, mock_config_entry)

    assert coordinator.ipp.request_timeout == REQUEST_TIMEOUT


async def test_printer_unreachable_keeps_last_known_values(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ipp: MagicMock,
) -> None:
    """Test the coordinator keeps the last known values when the printer goes unreachable.

    Printers on a home network are routinely switched off or in standby,
    which should not make every sensor go unavailable.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_ha_1000_series")
    assert state
    assert state.state == "idle"

    mock_ipp.printer.side_effect = IPPConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.test_ha_1000_series")
    assert state
    assert state.state == "idle"

    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is True

    mock_ipp.printer.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_ha_1000_series")
    assert state
    assert state.state == "idle"
