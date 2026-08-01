"""Tests for the Bosch SHC entity base classes."""

from unittest.mock import MagicMock

from boschshcpy import SHCDevice, SHCIntrusionSystem

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.bosch_shc.entity import SHCDomainEntity, SHCEntity
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


async def test_shc_domain_entity_via_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test SHCDomainEntity links its device to the SHC hub via via_device_id."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    hub_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "root-serial")},
        manufacturer="Bosch",
        name="Bosch SHC",
        model="SmartHomeController",
    )

    domain = MagicMock(spec=SHCIntrusionSystem)
    domain.id = "intrusion-id"
    domain.manufacturer = "Bosch"
    domain.device_model = "ISENS"
    domain.name = "Intrusion Detection System"

    entity = SHCDomainEntity(
        hass=hass, domain=domain, parent_id="root-serial", entry_id=entry.entry_id
    )

    assert entity.device_info is not None
    assert entity.device_info["via_device_id"] == hub_device.id
