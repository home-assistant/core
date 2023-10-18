"""Tests for the La Marzocco Update Entities."""


from unittest.mock import MagicMock

import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    UpdateDeviceClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_machine_firmware(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Machine Firmware."""

    state = hass.states.get("update.gs01234_machine_firmware")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == UpdateDeviceClass.FIRMWARE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Machine Firmware"
    assert state.attributes.get(ATTR_ICON) == "mdi:cloud-download"
    assert state.attributes.get(ATTR_INSTALLED_VERSION) == "1.1"
    assert state.attributes.get(ATTR_LATEST_VERSION) == "1.1"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_machine_firmware"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"


async def test_gateway_firmware(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Machine Firmware."""

    state = hass.states.get("update.gs01234_gateway_firmware")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == UpdateDeviceClass.FIRMWARE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Gateway Firmware"
    assert state.attributes.get(ATTR_ICON) == "mdi:cloud-download"
    assert state.attributes.get(ATTR_INSTALLED_VERSION) == "v2.2-rc0"
    assert state.attributes.get(ATTR_LATEST_VERSION) == "v3.1-rc4"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_gateway_firmware"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"
