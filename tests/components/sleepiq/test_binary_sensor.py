"""The tests for SleepIQ binary sensor platform."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.helpers import entity_registry as er


async def test_binary_sensors(hass, setup_entry):
    """Test the SleepIQ binary sensors."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert state.state == "on"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OCCUPANCY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 Is In Bed"

    entry = entity_registry.async_get("binary_sensor.sleepnumber_ile_test1_is_in_bed")
    assert entry
    assert entry.unique_id == "-31_Test1_is_in_bed"

    # Test the second binary sensor when the fixture is not loading the
    # -single bed data
    if not setup_entry:
        entry = entity_registry.async_get(
            "binary_sensor.sleepnumber_ile_test2_is_in_bed"
        )
        assert entry
        assert entry.unique_id == "-31_Test2_is_in_bed"

        state = hass.states.get("binary_sensor.sleepnumber_ile_test2_is_in_bed")
        assert state.state == "off"
        assert state.attributes.get(ATTR_ICON) == "mdi:bed-empty"
        assert (
            state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OCCUPANCY
        )
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "SleepNumber ILE Test2 Is In Bed"
        )
