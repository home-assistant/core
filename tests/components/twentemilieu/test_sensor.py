"""Tests for the Twente Milieu sensors."""
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.twentemilieu.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_waste_pickup_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Twente Milieu waste pickup sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.twente_milieu_christmas_tree_pickup")
    entry = entity_registry.async_get("sensor.twente_milieu_christmas_tree_pickup")
    assert entry
    assert state
    assert entry.unique_id == "twentemilieu_12345_tree"
    assert state.state == "2022-01-06"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Twente Milieu Christmas tree pickup"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert state.attributes.get(ATTR_ICON) == "mdi:pine-tree"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.twente_milieu_non_recyclable_waste_pickup")
    entry = entity_registry.async_get(
        "sensor.twente_milieu_non_recyclable_waste_pickup"
    )
    assert entry
    assert state
    assert entry.unique_id == "twentemilieu_12345_Non-recyclable"
    assert state.state == "2021-11-01"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Twente Milieu Non-recyclable waste pickup"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert state.attributes.get(ATTR_ICON) == "mdi:delete-empty"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.twente_milieu_organic_waste_pickup")
    entry = entity_registry.async_get("sensor.twente_milieu_organic_waste_pickup")
    assert entry
    assert state
    assert entry.unique_id == "twentemilieu_12345_Organic"
    assert state.state == "2021-11-02"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Twente Milieu Organic waste pickup"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert state.attributes.get(ATTR_ICON) == "mdi:delete-empty"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.twente_milieu_packages_waste_pickup")
    entry = entity_registry.async_get("sensor.twente_milieu_packages_waste_pickup")
    assert entry
    assert state
    assert entry.unique_id == "twentemilieu_12345_Plastic"
    assert state.state == "2021-11-03"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Twente Milieu Packages waste pickup"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert state.attributes.get(ATTR_ICON) == "mdi:delete-empty"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.twente_milieu_paper_waste_pickup")
    entry = entity_registry.async_get("sensor.twente_milieu_paper_waste_pickup")
    assert entry
    assert state
    assert entry.unique_id == "twentemilieu_12345_Paper"
    assert state.state == STATE_UNKNOWN
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Twente Milieu Paper waste pickup"
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATE
    assert state.attributes.get(ATTR_ICON) == "mdi:delete-empty"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "12345")}
    assert device_entry.manufacturer == "Twente Milieu"
    assert device_entry.name == "Twente Milieu"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.configuration_url == "https://www.twentemilieu.nl"
    assert not device_entry.model
    assert not device_entry.sw_version
