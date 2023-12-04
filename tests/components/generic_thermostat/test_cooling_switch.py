"""Test the Generic Thermostat on and off switching for cooling."""
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENT_SWITCH
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_set_target_temp_ac_off(hass: HomeAssistant, setup_comp_3) -> None:
    """Test if target temperature turn ac off."""
    calls = _setup_switch(hass, True)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 30)
    assert len(calls) == 2
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_set_target_temp_ac_on(hass: HomeAssistant, setup_comp_3) -> None:
    """Test if target temperature turn ac on."""
    calls = _setup_switch(hass, False)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_temp_change_ac_off_within_tolerance(
    hass: HomeAssistant, setup_comp_3
) -> None:
    """Test if temperature change doesn't turn ac off within tolerance."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 29.8)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_set_temp_change_ac_off_outside_tolerance(
    hass: HomeAssistant, setup_comp_3
) -> None:
    """Test if temperature change turn ac off."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 27)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_temp_change_ac_on_within_tolerance(
    hass: HomeAssistant, setup_comp_3
) -> None:
    """Test if temperature change doesn't turn ac on within tolerance."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 25.2)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_temp_change_ac_on_outside_tolerance(
    hass: HomeAssistant, setup_comp_3
) -> None:
    """Test if temperature change turn ac on."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH
