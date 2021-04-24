"""Tests for AVM Fritz!Box switch component."""
from datetime import timedelta
from unittest.mock import Mock

from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    ATTR_TEMPERATURE_UNIT,
    ATTR_TOTAL_CONSUMPTION,
    ATTR_TOTAL_CONSUMPTION_UNIT,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.components.switch import ATTR_CURRENT_POWER_W, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import MOCK_CONFIG, FritzDeviceSwitchMock

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake_name"


async def setup_fritzbox(hass: HomeAssistant, config: dict):
    """Set up mock AVM Fritz!Box."""
    assert await async_setup_component(hass, FB_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistant, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_CURRENT_POWER_W] == 5.678
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_STATE_DEVICE_LOCKED] == "fake_locked_device"
    assert state.attributes[ATTR_STATE_LOCKED] == "fake_locked"
    assert state.attributes[ATTR_TEMPERATURE] == "135"
    assert state.attributes[ATTR_TEMPERATURE_UNIT] == TEMP_CELSIUS
    assert state.attributes[ATTR_TOTAL_CONSUMPTION] == "1.234"
    assert state.attributes[ATTR_TOTAL_CONSUMPTION_UNIT] == ENERGY_KILO_WATT_HOUR


async def test_turn_on(hass: HomeAssistant, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_on.call_count == 1


async def test_turn_off(hass: HomeAssistant, fritz: Mock):
    """Test turn device off."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_off.call_count == 1


async def test_update(hass: HomeAssistant, fritz: Mock):
    """Test update without error."""
    device = FritzDeviceSwitchMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    assert device.update.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistant, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceSwitchMock()
    device.update.side_effect = HTTPError("Boom")
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    assert device.update.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 2
    assert fritz().login.call_count == 2
