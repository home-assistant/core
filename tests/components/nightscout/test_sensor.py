"""The sensor tests for the Nightscout platform."""

from homeassistant.components.nightscout.const import (
    ATTR_DELTA,
    ATTR_DEVICE,
    ATTR_DIRECTION,
    ATTR_SGV,
    MMOL_L,
)
from homeassistant.const import ATTR_DATE, ATTR_ICON, STATE_UNAVAILABLE

from tests.components.nightscout import (
    CONVERTED_MMOL_VALUES,
    GLUCOSE_READINGS,
    init_integration,
    init_integration_empty_response,
    init_integration_unavailable,
)


async def test_sensor_state(hass):
    """Test sensor state data."""
    await init_integration(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == str(
        GLUCOSE_READINGS[0].sgv  # pylint: disable=maybe-no-member
    )


async def test_sensor_state_options_changed(hass):
    """Test sensor state data with options changed."""
    await init_integration(hass, MMOL_L)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == str(CONVERTED_MMOL_VALUES[ATTR_SGV])


async def test_sensor_error(hass):
    """Test sensor state data."""
    await init_integration_unavailable(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == STATE_UNAVAILABLE


async def test_sensor_empty_response(hass):
    """Test sensor state data."""
    await init_integration_empty_response(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == STATE_UNAVAILABLE


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
    assert attr[ATTR_ICON] == "mdi:arrow-bottom-right"


async def test_sensor_attributes_options_changed(hass):
    """Test sensor attributes."""
    await init_integration(hass, MMOL_L)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    reading = GLUCOSE_READINGS[0]
    assert reading is not None

    attr = test_glucose_sensor.attributes
    assert attr[ATTR_DATE] == reading.date  # pylint: disable=maybe-no-member
    assert attr[ATTR_DELTA] == CONVERTED_MMOL_VALUES[ATTR_DELTA]
    assert attr[ATTR_DEVICE] == reading.device  # pylint: disable=maybe-no-member
    assert attr[ATTR_DIRECTION] == reading.direction  # pylint: disable=maybe-no-member
    assert attr[ATTR_ICON] == "mdi:arrow-bottom-right"
