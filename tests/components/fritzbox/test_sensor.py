"""Tests for AVM Fritz!Box sensor component."""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError
from syrupy import SnapshotAssertion

from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    FritzDeviceBinarySensorMock,
    FritzDeviceClimateMock,
    FritzDeviceSensorMock,
    FritzDeviceSwitchMock,
    FritzEntityBaseMock,
    set_devices,
    setup_config_entry,
)
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}"


@pytest.mark.parametrize(
    "device",
    [
        FritzDeviceBinarySensorMock,
        FritzDeviceClimateMock,
        FritzDeviceSensorMock,
        FritzDeviceSwitchMock,
    ],
)
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
    device: FritzEntityBaseMock,
) -> None:
    """Test setup of sensor platform for different device types."""
    device = device()

    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.SENSOR]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceSensorMock()
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
    device = FritzDeviceSensorMock()
    fritz().update_devices.side_effect = HTTPError("Boom")
    entry = await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 2

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 4
    assert fritz().login.call_count == 4


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    device = FritzDeviceSensorMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(f"{ENTITY_ID}_temperature")
    assert state

    new_device = FritzDeviceSensorMock()
    new_device.ain = "7890 1234"
    new_device.device_and_unit_id = ("7890 1234", None)
    new_device.name = "new_device"
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{SENSOR_DOMAIN}.new_device_temperature")
    assert state


@pytest.mark.parametrize(
    ("next_changes", "expected_states"),
    [
        (
            [0, 16],
            [STATE_UNKNOWN, STATE_UNKNOWN, STATE_UNKNOWN, STATE_UNKNOWN],
        ),
        (
            [0, 22],
            [STATE_UNKNOWN, STATE_UNKNOWN, STATE_UNKNOWN, STATE_UNKNOWN],
        ),
        (
            [1726855200, 16.0],
            ["2024-09-20T18:00:00+00:00", "16.0", PRESET_ECO, PRESET_COMFORT],
        ),
        (
            [1726855200, 22.0],
            ["2024-09-20T18:00:00+00:00", "22.0", PRESET_COMFORT, PRESET_ECO],
        ),
    ],
)
async def test_next_change_sensors(
    hass: HomeAssistant, fritz: Mock, next_changes: list, expected_states: list
) -> None:
    """Test next change sensors."""
    device = FritzDeviceClimateMock()
    device.nextchange_endperiod = next_changes[0]
    device.nextchange_temperature = next_changes[1]

    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    base_name = f"{SENSOR_DOMAIN}.{CONF_FAKE_NAME}"

    state = hass.states.get(f"{base_name}_next_scheduled_change_time")
    assert state
    assert state.state == expected_states[0]

    state = hass.states.get(f"{base_name}_next_scheduled_temperature")
    assert state
    assert state.state == expected_states[1]

    state = hass.states.get(f"{base_name}_next_scheduled_preset")
    assert state
    assert state.state == expected_states[2]

    state = hass.states.get(f"{base_name}_current_scheduled_preset")
    assert state
    assert state.state == expected_states[3]
