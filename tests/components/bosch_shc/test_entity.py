"""Tests for the Bosch SHC entity base classes."""

from unittest.mock import MagicMock

from boschshcpy import SHCDevice

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.bosch_shc.entity import SHCEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_shc_entity_via_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test SHCEntity links its device to the SHC hub via via_device_id."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "root-serial")},
        manufacturer="Bosch",
        name="Bosch SHC",
        model="SmartHomeController",
    )

    device = MagicMock(spec=SHCDevice)
    device.serial = "child-serial"
    device.manufacturer = "Bosch"
    device.device_model = "SWD"
    device.name = "Shutter Contact"
    device.id = "child-id"
    device.root_device_id = "root-serial"

    entity = SHCEntity(
        hass=hass, device=device, parent_id="root-serial", entry_id=entry.entry_id
    )

    assert entity.device_info is not None
    assert entity.device_info["via_device_id"] == hub_device.id


async def test_shc_entity_via_device_id_mismatch(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test SHCEntity sets up without a link when the hub identifier does not match.

    boschshcpy may render the hub identifier and a device's root_device_id
    differently, so the lookup can miss; setup must not crash in that case.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "hub-serial")},
        manufacturer="Bosch",
        name="Bosch SHC",
        model="SmartHomeController",
    )

    device = MagicMock(spec=SHCDevice)
    device.serial = "child-serial"
    device.manufacturer = "Bosch"
    device.device_model = "SWD"
    device.name = "Shutter Contact"
    device.id = "child-id"
    device.root_device_id = "root-serial-mismatch"

    entity = SHCEntity(
        hass=hass, device=device, parent_id="hub-serial", entry_id=entry.entry_id
    )

    assert entity.device_info is not None
    assert "via_device_id" not in entity.device_info
