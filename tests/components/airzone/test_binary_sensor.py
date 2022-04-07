"""The sensor tests for the Airzone platform."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.despacho_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.despacho_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.despacho_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_air_demand")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.dorm_ppal_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_problem")
    assert state.state == STATE_OFF
