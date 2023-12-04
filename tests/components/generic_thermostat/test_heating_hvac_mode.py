"""Test the Generic thermostat havc mode functionality for heating."""
from homeassistant.components.climate import DOMAIN, HVACMode
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENT_SENSOR, ENT_SWITCH
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_no_state_change_when_hvac_mode_off(
    hass: HomeAssistant, setup_comp_2
) -> None:
    """Test that the switch doesn't turn on when enabled is False."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_hvac_mode_heat(hass: HomeAssistant, setup_comp_2) -> None:
    """Test change mode from OFF to HEAT.

    Switch turns on when temp below setpoint and mode changes.
    """
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    calls = _setup_switch(hass, False)
    await common.async_set_hvac_mode(hass, HVACMode.HEAT)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_running_when_hvac_mode_is_off(hass: HomeAssistant, setup_comp_2) -> None:
    """Test that the switch turns off when enabled is set False."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_initial_hvac_off_force_heater_off(hass: HomeAssistant) -> None:
    """Ensure that restored state is coherent with real situation.

    'initial_hvac_mode: off' will force HVAC status, but we must be sure
    that heater don't keep on.
    """
    # switch is on
    calls = _setup_switch(hass, True)
    assert hass.states.get(ENT_SWITCH).state == STATE_ON

    _setup_sensor(hass, 16)

    await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test_thermostat",
                "heater": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
                "target_temp": 20,
                "initial_hvac_mode": HVACMode.OFF,
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.test_thermostat")
    # 'initial_hvac_mode' will force state but must prevent heather keep working
    assert state.state == HVACMode.OFF
    # heater must be switched off
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH
