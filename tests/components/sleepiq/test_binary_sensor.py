"""The tests for SleepIQ binary sensor platform."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.helpers import entity_registry as er

from tests.components.sleepiq import init_integration


async def test_binary_sensors(hass, requests_mock) -> None:
    """Test the SleepIQ binary sensors for a bed with two sides."""
    await init_integration(hass, requests_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert state.state == "on"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OCCUPANCY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 Is In Bed"

    state = hass.states.get("binary_sensor.sleepnumber_ile_test2_is_in_bed")
    assert state.state == "off"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed-empty"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OCCUPANCY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test2 Is In Bed"

    entry = entity_registry.async_get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert entry
    assert entry.unique_id == "-31_Test1_is_in_bed"

    entry = entity_registry.async_get("binary_sensor.sleepnumber_ile_test2_is_in_bed")
    assert entry
    assert entry.unique_id == "-31_Test2_is_in_bed"


async def test_binary_sensors_single(hass, requests_mock) -> None:
    """Test the SleepIQ binary sensor for a single bed."""
    await init_integration(hass, requests_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert state
    assert state.state == "on"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OCCUPANCY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 Is In Bed"

    entry = entity_registry.async_get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert entry
    assert entry.unique_id == "-31_Test1_is_in_bed"
