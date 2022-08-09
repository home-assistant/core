"""The sensor tests for the Airzone platform."""

from aioairzone.const import API_ERROR_LOW_BATTERY

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_airzone_create_binary_sensors(hass: HomeAssistant) -> None:
    """Test creation of binary sensors."""

    await async_init_integration(hass)

    # Systems
    state = hass.states.get("binary_sensor.system_1_problem")
    assert state.state == STATE_OFF

    # Zones
    state = hass.states.get("binary_sensor.despacho_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.despacho_battery_low")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.despacho_floor_demand")
    assert state is None

    state = hass.states.get("binary_sensor.despacho_problem")
    assert state.state == STATE_ON
    assert state.attributes.get("errors") == [API_ERROR_LOW_BATTERY]

    state = hass.states.get("binary_sensor.dorm_1_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_battery_low")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_floor_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_1_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_battery_low")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_2_floor_demand")
    assert state is None

    state = hass.states.get("binary_sensor.dorm_2_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_air_demand")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.dorm_ppal_battery_low")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.dorm_ppal_floor_demand")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.dorm_ppal_problem")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_air_demand")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.salon_battery_low")
    assert state is None

    state = hass.states.get("binary_sensor.salon_floor_demand")
    assert state is None

    state = hass.states.get("binary_sensor.salon_problem")
    assert state.state == STATE_OFF
