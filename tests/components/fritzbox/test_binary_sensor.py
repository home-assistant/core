"""Tests for AVM Fritz!Box binary sensor component."""

from datetime import timedelta
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError
from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import FritzDeviceBinarySensorMock, set_devices, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = f"{BINARY_SENSOR_DOMAIN}.{CONF_FAKE_NAME}"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform."""
    device = FritzDeviceBinarySensorMock()
    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.BINARY_SENSOR]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_is_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test state of platform."""
    device = FritzDeviceBinarySensorMock()
    device.present = False
    await setup_config_entry(
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
    await setup_config_entry(
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
    await setup_config_entry(
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
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(f"{ENTITY_ID}_alarm")
    assert state

    new_device = FritzDeviceBinarySensorMock()
    new_device.ain = "7890 1234"
    new_device.device_and_unit_id = ("7890 1234", None)
    new_device.name = "new_device"
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.new_device_alarm")
    assert state
