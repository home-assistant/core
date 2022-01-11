"""The tests for SleepIQ sensor platform."""
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.helpers import entity_registry as er

from tests.components.sleepiq import init_integration


async def test_sensors(hass, requests_mock) -> None:
    """Test the SleepIQ binary sensors for a bed with two sides."""
    await init_integration(hass, requests_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("sensor.sleepnumber_ile_test1_sleepnumber")
    assert state.state == "40"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test1 SleepNumber"
    )

    state = hass.states.get("sensor.sleepnumber_ile_test2_sleepnumber")
    assert state.state == "80"
    assert state.attributes.get(ATTR_ICON) == "mdi:bed"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "SleepNumber ILE Test2 SleepNumber"
    )

    entry = entity_registry.async_get("sensor.sleepnumber_ile_test1_sleepnumber")
    assert entry
    assert entry.unique_id == "-31_Test1_sleep_number"

    entry = entity_registry.async_get("sensor.sleepnumber_ile_test2_sleepnumber")
    assert entry
    assert entry.unique_id == "-31_Test2_sleep_number"


async def test_sensors_single(hass, requests_mock) -> None:
    """Test the SleepIQ binary sensor for a single bed."""
    await init_integration(hass, requests_mock)

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
