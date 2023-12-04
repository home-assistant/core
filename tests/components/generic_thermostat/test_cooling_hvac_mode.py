"""Test the Generic thermostat havc mode functionality for cooling."""
from homeassistant.components.climate import PRESET_AWAY, HVACMode
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENT_SWITCH, ENTITY
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_turn_away_mode_on_cooling(hass: HomeAssistant, setup_comp_3) -> None:
    """Test the setting away mode when cooling."""
    _setup_switch(hass, True)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 19)
    await common.async_set_preset_mode(hass, PRESET_AWAY)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == 30


async def test_hvac_mode_cool(hass: HomeAssistant, setup_comp_3) -> None:
    """Test change mode from OFF to COOL.

    Switch turns on when temp below setpoint and mode changes.
    """
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    calls = _setup_switch(hass, False)
    await common.async_set_hvac_mode(hass, HVACMode.COOL)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_running_when_operating_mode_is_off_2(
    hass: HomeAssistant, setup_comp_3
) -> None:
    """Test that the switch turns off when enabled is set False."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_no_state_change_when_operation_mode_off_2(
    hass: HomeAssistant, setup_comp_3
) -> None:
    """Test that the switch doesn't turn on when enabled is False."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 0
