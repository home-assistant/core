"""Tests for the Tedee Sensors."""


from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASS_BATTERY,
    SensorStateClass,
)
from homeassistant.components.tedee.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_battery(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test tedee battery sensor."""
    state = hass.states.get("sensor.lock_1a2b_battery")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_BATTERY
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Lock-1A2B Battery"
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "%"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "12345-battery-sensor"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "12345")}
    assert device.manufacturer == "tedee"
    assert device.name == "Lock-1A2B"
    assert device.model == "Tedee PRO"
