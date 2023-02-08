"""Tests for the Elgato sensor platform."""

import pytest

from homeassistant.components.elgato.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory


@pytest.mark.parametrize("device_fixtures", ["key-light-mini"])
@pytest.mark.usefixtures(
    "device_fixtures",
    "entity_registry_enabled_by_default",
    "init_integration",
    "mock_elgato",
)
async def test_battery_sensor(hass: HomeAssistant) -> None:
    """Test the Elgato battery sensor."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.frenck_battery")
    assert state
    assert state.state == "78.57"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck Battery"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert not state.attributes.get(ATTR_ICON)

    entry = entity_registry.async_get("sensor.frenck_battery")
    assert entry
    assert entry.unique_id == "GW24L1A02987_battery"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert entry.options == {"sensor": {"suggested_display_precision": 0}}

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.configuration_url is None
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }
    assert device_entry.entry_type is None
    assert device_entry.identifiers == {(DOMAIN, "GW24L1A02987")}
    assert device_entry.manufacturer == "Elgato"
    assert device_entry.model == "Elgato Key Light Mini"
    assert device_entry.name == "Frenck"
    assert device_entry.sw_version == "1.0.4 (229)"
    assert device_entry.hw_version == "202"
