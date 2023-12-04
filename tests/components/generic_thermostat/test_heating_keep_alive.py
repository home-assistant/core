"""Test the Generic Thermostat keep-alive functionality for heating."""
import datetime

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.climate import common
from tests.components.generic_thermostat.const import ENT_SWITCH
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_temp_change_heater_trigger_on_long_enough_2(
    hass: HomeAssistant, setup_comp_8
) -> None:
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, True)
    await hass.async_block_till_done()
    _setup_sensor(hass, 20)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    test_time = datetime.datetime.now(dt_util.UTC)
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_temp_change_heater_trigger_off_long_enough_2(
    hass: HomeAssistant, setup_comp_8
) -> None:
    """Test if turn on signal is sent at keep-alive intervals."""
    calls = _setup_switch(hass, False)
    await hass.async_block_till_done()
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    await common.async_set_temperature(hass, 25)
    test_time = datetime.datetime.now(dt_util.UTC)
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=5))
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, test_time + datetime.timedelta(minutes=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH
