"""Tests for PowerShades background discovery."""

from unittest.mock import patch

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.components.powershades.discovery import DISCOVERY_INTERVAL
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_periodic_scan_creates_flow_and_refreshes_loaded_entries(
    hass: HomeAssistant, config_entry, mock_device_info
) -> None:
    """A periodic scan starts discovery flows for new devices and refreshes loaded entries."""
    coordinator = config_entry.runtime_data
    call_count_before = coordinator.connection.async_request.call_count

    with patch(
        "homeassistant.components.powershades.discovery.async_discover_devices",
        return_value=[{"ip": "192.168.1.99", "serial": 99999, "model": 1}],
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + DISCOVERY_INTERVAL)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(
        flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY for flow in flows
    )

    assert coordinator.connection.async_request.call_count > call_count_before
