"""Tests for AVM Fritz!Box binary sensor component."""

from datetime import timedelta
from unittest import mock
from unittest.mock import Mock

from requests.exceptions import HTTPError

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDeviceClass
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_DEVICES,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import FritzDeviceBinarySensorMock, set_devices, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock) -> None:
    """Test setup of platform."""
    device = FritzDeviceBinarySensorMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(f"{ENTITY_ID}_alarm")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Alarm"
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.WINDOW
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{ENTITY_ID}_button_lock_on_device")
    assert state
    assert state.state == STATE_OFF
    assert (
        state.attributes[ATTR_FRIENDLY_NAME]
        == f"{CONF_FAKE_NAME} Button lock on device"
    )
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.LOCK
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{ENTITY_ID}_button_lock_via_ui")
    assert state
    assert state.state == STATE_OFF
    assert (
        state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Button lock via UI"
    )
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.LOCK
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get(f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}_battery")
    assert state
    assert state.state == "23"
    assert state.attributes[ATTR_FRIENDLY_NAME] == f"{CONF_FAKE_NAME} Battery"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ATTR_STATE_CLASS not in state.attributes


async def test_is_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test state of platform."""
    device = FritzDeviceBinarySensorMock()
    device.present = False
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(f"{ENTITY_ID}_alarm")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(f"{ENTITY_ID}_button_lock_on_device")
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(f"{ENTITY_ID}_button_lock_via_ui")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceBinarySensorMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert fritz().update_devices.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 1


async def test_update_error(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update with error."""
    device = FritzDeviceBinarySensorMock()
    device.update.side_effect = [mock.DEFAULT, HTTPError("Boom")]
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    assert fritz().update_devices.call_count == 1
    assert fritz().login.call_count == 1

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 1


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    device = FritzDeviceBinarySensorMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(f"{ENTITY_ID}_alarm")
    assert state

    new_device = FritzDeviceBinarySensorMock()
    new_device.ain = "7890 1234"
    new_device.name = "new_device"
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DOMAIN}.new_device_alarm")
    assert state
