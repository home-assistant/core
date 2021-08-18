"""Tests for AVM Fritz!Box switch component."""
from datetime import timedelta
from unittest.mock import Mock

from requests.exceptions import HTTPError

from homeassistant.components.fritzbox.const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.components.switch import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICES,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import FritzDeviceSwitchMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == CONF_FAKE_NAME
    assert state.attributes[ATTR_STATE_DEVICE_LOCKED] == "fake_locked_device"
    assert state.attributes[ATTR_STATE_LOCKED] == "fake_locked"
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_temperature")
    assert state
    assert state.state == "1.23"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Temperature"
    assert state.attributes[ATTR_STATE_DEVICE_LOCKED] == "fake_locked_device"
    assert state.attributes[ATTR_STATE_LOCKED] == "fake_locked"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_power_consumption")
    assert state
    assert state.state == "5.678"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Power Consumption"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == POWER_WATT
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_total_energy")
    assert state
    assert state.state == "1.234"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Total Energy"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_KILO_WATT_HOUR
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_TOTAL_INCREASING


async def test_turn_on(hass: HomeAssistant, fritz: Mock):
    """Test turn device on."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_on.call_count == 1


async def test_turn_off(hass: HomeAssistant, fritz: Mock):
    """Test turn device off."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_switch_state_off.call_count == 1


async def test_update(hass: HomeAssistant, fritz: Mock):
    """Test update without error."""
    device = FritzDeviceSwitchMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
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
    assert not await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert device.update.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 2
    assert fritz().login.call_count == 2
