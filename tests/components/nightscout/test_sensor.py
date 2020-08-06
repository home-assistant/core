"""The sensor tests for the Nightscout platform."""

from homeassistant.components.nightscout.const import (
    ATTR_DATE,
    ATTR_DELTA,
    ATTR_DEVICE,
    ATTR_DIRECTION,
    ATTR_SVG,
)
from homeassistant.const import ATTR_ICON

from tests.components.nightscout import GLUCOSE_READINGS, init_integration


async def test_sensor_state(hass):
    """Test sensor state data."""
    await init_integration(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == str(
        GLUCOSE_READINGS[0].sgv  # pylint: disable=maybe-no-member
    )


async def test_sensor_attributes(hass):
    """Test sensor attributes."""
    await init_integration(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    reading = GLUCOSE_READINGS[0]
    assert reading is not None

    attr = test_glucose_sensor.attributes
    assert attr[ATTR_DATE] == reading.date  # pylint: disable=maybe-no-member
    assert attr[ATTR_DELTA] == reading.delta  # pylint: disable=maybe-no-member
    assert attr[ATTR_DEVICE] == reading.device  # pylint: disable=maybe-no-member
    assert attr[ATTR_DIRECTION] == reading.direction  # pylint: disable=maybe-no-member
    assert attr[ATTR_SVG] == reading.sgv  # pylint: disable=maybe-no-member
    assert attr[ATTR_ICON] == "mdi:arrow-bottom-right"
