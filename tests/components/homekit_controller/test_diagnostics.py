"""Test homekit_controller diagnostics."""

from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.homekit_controller.const import KNOWN_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_accessories_from_file, setup_test_accessories

IP_CONNECTION_DATA = {
    "AccessoryIP": "192.168.1.10",
    "AccessoryIPs": ["192.168.1.10", "2001:db8::10", "fd00::10"],
    "AccessoryPort": 51826,
}


async def test_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, _ = await setup_test_accessories(hass, accessories)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, **IP_CONNECTION_DATA}
    )

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag == snapshot(
        exclude=props("last_changed", "last_reported", "last_updated")
    )


async def test_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a device entry."""
    accessories = await setup_accessories_from_file(hass, "koogeek_ls1.json")
    config_entry, _ = await setup_test_accessories(hass, accessories)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, **IP_CONNECTION_DATA}
    )

    connection = hass.data[KNOWN_DEVICES]["00:00:00:00:00:00"]
    device = device_registry.async_get(connection.devices[1])

    diag = await get_diagnostics_for_device(hass, hass_client, config_entry, device)

    assert diag == snapshot(
        exclude=props("last_changed", "last_reported", "last_updated")
    )


async def test_child_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a child device returns the diagnostics of its parent device."""
    accessories = await setup_accessories_from_file(hass, "eve_energy_strip.json")
    config_entry, _ = await setup_test_accessories(hass, accessories)

    connection = hass.data[KNOWN_DEVICES]["00:00:00:00:00:00"]
    parent_device = device_registry.async_get(connection.devices[1])
    child_device = device_registry.async_get(connection.child_devices[(1, 13)])

    parent_diag = await get_diagnostics_for_device(
        hass, hass_client, config_entry, parent_device
    )
    child_diag = await get_diagnostics_for_device(
        hass, hass_client, config_entry, child_device
    )

    assert child_diag == parent_diag
    assert [
        child_device["name"] for child_device in parent_diag["device"]["child_devices"]
    ] == ["Eve Energy Strip 1", "Eve Energy Strip 2", "Eve Energy Strip 3"]
