"""Tests for the La Marzocco Binary Sensors."""


from unittest.mock import MagicMock

import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_drink_stats(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco Drink Stats."""
    state = hass.states.get("sensor.gs01234_drink_statistics")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "GS01234 Drink Statistics"
    assert state.attributes.get(ATTR_ICON) == "mdi:chart-line"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "drinks"
    # test extra attributes
    assert state.attributes.get("drinks_k1") == 13
    assert state.attributes.get("drinks_k2") == 2
    assert state.attributes.get("drinks_k3") == 42
    assert state.attributes.get("drinks_k4") == 34
    assert state.attributes.get("total_flushing") == 69
    assert state.state == "82"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.unique_id == "GS01234_drink_stats"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "GS01234")}
    assert device.manufacturer == "La Marzocco"
    assert device.name == "GS01234"
    assert device.sw_version == "1.1"
