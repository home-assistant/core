"""Test the Generic Thermostat on and off switching for heating."""
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENT_SWITCH
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_set_target_temp_heater_on(hass: HomeAssistant, setup_comp_2) -> None:
    """Test if target temperature turn heater on."""
    calls = _setup_switch(hass, False)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 30)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_set_target_temp_heater_off(hass: HomeAssistant, setup_comp_2) -> None:
    """Test if target temperature turn heater off."""
    calls = _setup_switch(hass, True)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    assert len(calls) == 2
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_temp_change_heater_on_within_tolerance(
    hass: HomeAssistant, setup_comp_2
) -> None:
    """Test if temperature change doesn't turn on within tolerance."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 29)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_temp_change_heater_on_outside_tolerance(
    hass: HomeAssistant, setup_comp_2
) -> None:
    """Test if temperature change turn heater on outside cold tolerance."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 27)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_temp_change_heater_off_within_tolerance(
    hass: HomeAssistant, setup_comp_2
) -> None:
    """Test if temperature change doesn't turn off within tolerance."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 33)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_temp_change_heater_off_outside_tolerance(
    hass: HomeAssistant, setup_comp_2
) -> None:
    """Test if temperature change turn heater off outside hot tolerance."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 35)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH
