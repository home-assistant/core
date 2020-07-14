"""Test sensor of the growatt_rs232 integration."""
from datetime import timedelta

from growattRS232 import ATTR_SERIAL_NUMBER, ATTR_STATUS_CODE

from homeassistant.components.growatt_rs232.const import SENSOR_TYPES
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE
from homeassistant.util.dt import utcnow

from tests.async_mock import patch
from tests.common import async_fire_time_changed
from tests.components.growatt_rs232 import init_integration
from tests.components.growatt_rs232.const import DATA_NORMAL, PATCH, VALUES


async def test_sensors(hass):
    """Test states of the sensors."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    for sensor_key, sensor_value in SENSOR_TYPES.items():
        sensor = f"sensor.{VALUES[ATTR_SERIAL_NUMBER]}_{sensor_key}"
        state = hass.states.get(sensor)
        assert state
        assert state.attributes.get(ATTR_ICON) == sensor_value[ATTR_ICON]
        assert (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == sensor_value[ATTR_UNIT_OF_MEASUREMENT]
        )
        assert state.state == str(VALUES[sensor_key])

        entry = registry.async_get(sensor)
        assert entry
        assert entry.unique_id == f"{VALUES[ATTR_SERIAL_NUMBER]}_{sensor_key}"


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when device is offline."""
    sensor = f"sensor.{VALUES[ATTR_SERIAL_NUMBER]}_{ATTR_STATUS_CODE}"

    await init_integration(hass)

    state = hass.states.get(sensor)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == str(VALUES[ATTR_STATUS_CODE])

    future = utcnow() + timedelta(minutes=5)
    with patch(PATCH, side_effect=ConnectionError()):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(sensor)
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=10)
    with patch(
        PATCH, return_value=DATA_NORMAL,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(sensor)
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == str(VALUES[ATTR_STATUS_CODE])
