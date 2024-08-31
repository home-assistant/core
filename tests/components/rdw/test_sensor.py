"""Tests for the sensors provided by the RDW integration."""

from homeassistant.components.rdw.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_vehicle_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the RDW vehicle sensors."""
    state = hass.states.get("sensor.skoda_11zkz3_apk_expiration")
    entry = entity_registry.async_get("sensor.skoda_11zkz3_apk_expiration")
    assert entry
    assert state
    assert entry.unique_id == "11ZKZ3_apk_expiration"
    assert state.state == "2022-01-04"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Skoda 11ZKZ3 APK expiration"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert ATTR_ICON not in state.attributes
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.skoda_11zkz3_ascription_date")
    entry = entity_registry.async_get("sensor.skoda_11zkz3_ascription_date")
    assert entry
    assert state
    assert entry.unique_id == "11ZKZ3_ascription_date"
    assert state.state == "2021-11-04"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Skoda 11ZKZ3 Ascription date"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert ATTR_ICON not in state.attributes
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "11ZKZ3")}
    assert device_entry.manufacturer == "Skoda"
    assert device_entry.name == "Skoda 11ZKZ3"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.model == "Citigo"
    assert (
        device_entry.configuration_url
        == "https://ovi.rdw.nl/default.aspx?kenteken=11ZKZ3"
    )
    assert not device_entry.sw_version
