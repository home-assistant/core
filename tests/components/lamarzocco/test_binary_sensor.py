"""Tests for the La Marzocco Binary Sensors."""


from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import STATE_OFF, BinarySensorDeviceClass
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_water_reservoir(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Water Reservoir Detection."""

    state = hass.states.get("binary_sensor.gs01234_water_reservoir")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PROBLEM
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Water Reservoir"
    assert state.attributes.get(ATTR_ICON) == "mdi:water-well"
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_water_reservoir"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"


async def test_brew_active(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Brew Active Sensor."""

    state = hass.states.get("binary_sensor.gs01234_brew_active")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.RUNNING
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Brew Active"
    assert state.attributes.get(ATTR_ICON) == "mdi:cup-water"
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_brew_active"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"
