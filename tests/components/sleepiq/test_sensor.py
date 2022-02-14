"""The tests for SleepIQ sensor platform."""
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.helpers import entity_registry as er


async def test_sensors(hass, setup_entry):
    """Test the SleepIQ binary sensors for a bed with two sides."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.sleepnumber_ile_test1_sleepnumber")
    assert state.state == "40"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 SleepNumber"
    )

    entry = entity_registry.async_get("sensor.sleepnumber_ile_test1_sleepnumber")
    assert entry
    assert entry.unique_id == "-31_Test1_sleep_number"

    if not setup_entry:
        state = hass.states.get("sensor.sleepnumber_ile_test2_sleepnumber")
        assert state.state == "80"
        assert state.attributes.get(ATTR_ICON) == "mdi:bed"
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME)
            == "SleepNumber ILE Test2 SleepNumber"
        )

        entry = entity_registry.async_get("sensor.sleepnumber_ile_test2_sleepnumber")
        assert entry
        assert entry.unique_id == "-31_Test2_sleep_number"
