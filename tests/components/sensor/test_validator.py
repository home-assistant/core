"""Test sensor validation."""
from homeassistant.components.sensor.validator import async_validate_entities
from homeassistant.components.validator import Report
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT


async def test_validate_entities(hass):
    """Test validate entities."""
    hass.states.async_set(
        "sensor.invalid_state", "hello", {ATTR_UNIT_OF_MEASUREMENT: "C"}
    )
    hass.states.async_set("sensor.valid_int", "3", {ATTR_UNIT_OF_MEASUREMENT: "C"})
    hass.states.async_set("sensor.valid_float", "15.6", {ATTR_UNIT_OF_MEASUREMENT: "C"})
    report = Report()
    await async_validate_entities(hass, report)
    assert len(report.entities) == 1
    assert report.entities.get("sensor.invalid_state", []) == [
        "State with a unit of measurement should be numeric. Got 'hello'"
    ]
