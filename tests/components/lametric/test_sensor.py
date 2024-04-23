"""Tests for the LaMetric sensor platform."""

import pytest

from homeassistant.components.lametric.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)


async def test_wifi_signal(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LaMetric Wi-Fi sensor."""
    state = hass.states.get("sensor.frenck_s_lametric_wi_fi_signal")
    assert state
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck's LaMetric Wi-Fi signal"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.state == "21"

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.entity_category is EntityCategory.DIAGNOSTIC
    assert entry.unique_id == "SA110405124500W00BS9-rssi"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url is None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "SA110405124500W00BS9")}
    assert device.manufacturer == "LaMetric Inc."
    assert device.name == "Frenck's LaMetric"
    assert device.sw_version == "2.2.2"
