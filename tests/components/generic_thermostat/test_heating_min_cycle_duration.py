"""Test the Generic Thermostat minimum cycle duration functionality for heating."""
import datetime

from freezegun import freeze_time

from homeassistant.components.climate import HVACMode
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.util import dt as dt_util

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENT_SWITCH
from tests.components.generic_thermostat.shared import _setup_sensor, _setup_switch


async def test_temp_change_heater_trigger_off_not_long_enough(
    hass: HomeAssistant, setup_comp_6
) -> None:
    """Test if temp change doesn't turn heater off because of time."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_temp_change_heater_trigger_on_not_long_enough(
    hass: HomeAssistant, setup_comp_6
) -> None:
    """Test if temp change doesn't turn heater on because of time."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_temp_change_heater_trigger_on_long_enough(
    hass: HomeAssistant, setup_comp_6
) -> None:
    """Test if temperature change turn heater on after min cycle."""
    fake_changed = datetime.datetime(1970, 11, 11, 11, 11, 11, tzinfo=dt_util.UTC)
    with freeze_time(fake_changed):
        calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH


async def test_temp_change_heater_trigger_off_long_enough(
    hass: HomeAssistant, setup_comp_6
) -> None:
    """Test if temperature change turn heater off after min cycle."""
    fake_changed = datetime.datetime(1970, 11, 11, 11, 11, 11, tzinfo=dt_util.UTC)
    with freeze_time(fake_changed):
        calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_mode_change_heater_trigger_off_not_long_enough(
    hass: HomeAssistant, setup_comp_6
) -> None:
    """Test if mode change turns heater off despite minimum cycle."""
    calls = _setup_switch(hass, True)
    await common.async_set_temperature(hass, 25)
    _setup_sensor(hass, 30)
    await hass.async_block_till_done()
    assert len(calls) == 0
    await common.async_set_hvac_mode(hass, HVACMode.OFF)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "homeassistant"
    assert call.service == SERVICE_TURN_OFF
    assert call.data["entity_id"] == ENT_SWITCH


async def test_mode_change_heater_trigger_on_not_long_enough(
    hass: HomeAssistant, setup_comp_6
) -> None:
    """Test if mode change turns heater on despite minimum cycle."""
    calls = _setup_switch(hass, False)
    await common.async_set_temperature(hass, 30)
    _setup_sensor(hass, 25)
    await hass.async_block_till_done()
    assert len(calls) == 0
    await common.async_set_hvac_mode(hass, HVACMode.HEAT)
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == "homeassistant"
    assert call.service == SERVICE_TURN_ON
    assert call.data["entity_id"] == ENT_SWITCH
