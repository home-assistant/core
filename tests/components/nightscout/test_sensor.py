"""The sensor tests for the Nightscout platform."""

from homeassistant.components.nightscout.const import (
    ATTR_DELTA,
    ATTR_DEVICE,
    ATTR_DIRECTION,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASS_BATTERY,
    STATE_CLASS_MEASUREMENT,
)
from homeassistant.const import ATTR_DATE, ATTR_DEVICE_CLASS, ATTR_ICON
from homeassistant.helpers import device_registry as dr

from . import (
    GLUCOSE_READINGS,
    init_integration,
    init_integration_empty_response,
    init_integration_unavailable,
)

# Glucose sensor tests


async def test_glucose_sensor_state(hass):
    """Test glucose sensor state data."""
    await init_integration(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor.state == str(
        GLUCOSE_READINGS[0].sgv  # pylint: disable=maybe-no-member
    )


async def test_glucose_sensor_error(hass):
    """Test glucose sensor state data."""
    await init_integration_unavailable(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor is None


async def test_glucose_sensor_empty_response(hass):
    """Test glucose sensor state data."""
    await init_integration_empty_response(hass)

    test_glucose_sensor = hass.states.get("sensor.blood_sugar")
    assert test_glucose_sensor is None


async def test_glucose_sensor_attributes(hass):
    """Test glucose sensor attributes."""
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


# Device Battery sensor tests


async def test_battery_sensor_state(hass):
    """Test battery sensor state data."""
    config_entry = await init_integration(hass)

    test_tomato_sensor = hass.states.get("sensor.tomato")
    assert test_tomato_sensor.state == "70"
    assert test_tomato_sensor.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_BATTERY
    assert test_tomato_sensor.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    tomato_device_info = dr.async_get(hass).async_get_device(
        {("nightscout", f"{config_entry.unique_id}_{test_tomato_sensor.name}")}
    )
    assert tomato_device_info.model == "BRIDGE"

    test_samsung_sensor = hass.states.get("sensor.samsung_sm_n986b")
    assert test_samsung_sensor.state == "68"
    assert test_samsung_sensor.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_BATTERY
    assert test_samsung_sensor.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
    samsung_device_info = dr.async_get(hass).async_get_device(
        {("nightscout", f"{config_entry.unique_id}_{test_samsung_sensor.name}")}
    )
    assert samsung_device_info.model == "PHONE"
