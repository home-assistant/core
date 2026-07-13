"""Tests for the SwitchBee Smart Home integration init."""

import json
from unittest.mock import patch

from homeassistant.components.switchbee.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_load_fixture


async def test_central_unit_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the central unit device carries the MAC and links the zone devices."""
    coordinator_data = json.loads(
        await async_load_fixture(hass, "switchbee.json", DOMAIN)
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "switchbee.api.polling.CentralUnitPolling.get_configuration",
            return_value=coordinator_data,
        ),
        patch(
            "switchbee.api.polling.CentralUnitPolling.fetch_states", return_value=None
        ),
        patch("switchbee.api.polling.CentralUnitPolling._login", return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    central_unit = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac("A8-21-08-E7-67-B6"))}
    )
    assert central_unit is not None
    assert central_unit.identifiers == {(DOMAIN, "Residence (None)")}
    assert central_unit.manufacturer == "SwitchBee"
    assert central_unit.name == "Residence"

    zone_devices = [
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.id != central_unit.id
    ]
    assert zone_devices
    assert all(device.via_device_id == central_unit.id for device in zone_devices)
