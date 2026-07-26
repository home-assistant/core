"""Tests for the SwitchBee Smart Home integration init."""

import pytest

from homeassistant.components.switchbee.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_central_unit")
async def test_central_unit_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the central unit device carries the MAC and links the zone devices."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    central_unit = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "a8:21:08:e7:67:b6")}
    )
    assert central_unit is not None
    assert central_unit.identifiers == {(DOMAIN, "300F123456")}
    assert central_unit.manufacturer == "SwitchBee"
    assert central_unit.name == "Residence"

    zone_devices = [
        device
        for device in dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        if device.id != central_unit.id
    ]
    assert len(zone_devices) == 2
    assert all(device.via_device_id == central_unit.id for device in zone_devices)
