"""The sensor tests for the Airzone platform."""

from homeassistant.const import STATE_OFF, STATE_ON

from .util import async_init_integration


async def test_airzone_create_binary_sensors(hass):
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.despacho_demand")
    assert state.state == STATE_OFF
    assert state.attributes.get("air") == 0
    assert state.attributes.get("floor") == 0

    state = hass.states.get("binary_sensor.despacho_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_demand")
    assert state.state == STATE_OFF
    assert state.attributes.get("air") == 0
    assert state.attributes.get("floor") == 0

    state = hass.states.get("binary_sensor.dorm_1_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_demand")
    assert state.state == STATE_OFF
    assert state.attributes.get("air") == 0
    assert state.attributes.get("floor") == 0

    state = hass.states.get("binary_sensor.dorm_2_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_demand")
    assert state.state == STATE_ON
    assert state.attributes.get("air") == 1
    assert state.attributes.get("floor") == 0

    state = hass.states.get("binary_sensor.dorm_ppal_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_demand")
    assert state.state == STATE_OFF
    assert state.attributes.get("air") == 0
    assert state.attributes.get("floor") == 0

    state = hass.states.get("binary_sensor.salon_problem")
    assert state.state == STATE_OFF
