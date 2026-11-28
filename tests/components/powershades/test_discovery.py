"""Tests for PowerShades background discovery."""

from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.components.powershades.discovery import DISCOVERY_INTERVAL
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration


async def test_periodic_scan_creates_flow_and_refreshes_loaded_entries(
    hass: HomeAssistant,
    mock_discover_devices: AsyncMock,
    mock_powershades_connection: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_device_info: AsyncMock,
) -> None:
    """A periodic scan starts discovery flows for new devices and refreshes loaded entries."""
    await setup_integration(hass, mock_config_entry)
    call_count_before = mock_powershades_connection.async_request.call_count
    mock_discover_devices.return_value = [
        {"ip": "192.168.1.99", "serial": 99999, "model": 1}
    ]

    async_fire_time_changed(hass, dt_util.utcnow() + DISCOVERY_INTERVAL)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(
        flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY for flow in flows
    )
    assert mock_powershades_connection.async_request.call_count > call_count_before
