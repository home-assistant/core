"""Tests for AVM Fritz!Box binary sensor component."""
from datetime import timedelta
from unittest import mock

from requests.exceptions import HTTPError

from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import MOCK_CONFIG, FritzDeviceBinarySensorMock

from tests.async_mock import Mock
from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake_name"


async def setup_fritzbox(hass: HomeAssistantType, config: dict):
    """Set up mock AVM Fritz!Box."""
    assert await async_setup_component(hass, FB_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistantType, fritz: Mock):
    """Test setup of platform."""
    device = FritzDeviceBinarySensorMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake_name"
    assert state.attributes[ATTR_DEVICE_CLASS] == "window"


async def test_is_off(hass: HomeAssistantType, fritz: Mock):
    """Test state of platform."""
    device = FritzDeviceBinarySensorMock()
    device.present = False
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.state == STATE_OFF


async def test_update(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceBinarySensorMock()
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert device.update.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistantType, fritz: Mock):
    """Test update with error."""
    device = FritzDeviceBinarySensorMock()
    device.update.side_effect = [mock.DEFAULT, HTTPError("Boom")]
    fritz().get_devices.return_value = [device]

    await setup_fritzbox(hass, MOCK_CONFIG)

    assert device.update.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert device.update.call_count == 2
    assert fritz().login.call_count == 2
